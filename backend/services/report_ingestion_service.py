import os
import logging
import shutil
import json
from datetime import datetime
from typing import TYPE_CHECKING, Tuple, Optional, List

from .parsing_service import ParsingService
from .gemini_service import GeminiService

if TYPE_CHECKING:
    from .google_drive_service import GoogleDriveService
    from .data_access_layer import DataAccessLayer

logger = logging.getLogger(__name__)

SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SERVICE_DIR)
TEMP_DOWNLOAD_DIR = os.path.join(BACKEND_DIR, 'data', 'temp_downloads')

os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)
# Initial log about TEMP_DOWNLOAD_DIR is at module level, might not be JSON unless root logger is configured before this module is imported.
# This is usually fine, as critical operational logs will be from methods.

class ReportIngestionService:
    def __init__(self,
                 drive_service: 'Optional[GoogleDriveService]',
                 dal: 'DataAccessLayer',
                 parsing_service: 'ParsingService',
                 gemini_service: 'GeminiService'):
        self.drive_service = drive_service
        self.dal = dal
        self.parsing_service = parsing_service
        self.gemini_service = gemini_service
        # This log will be JSON formatted if main.py's lifespan configures logging before this service is instantiated.
        logger.info(
            "報告擷取服務 (ReportIngestionService) 已初始化。",
            extra={"props": {"service_name": "ReportIngestionService", "status": "initialized"}}
        )

    async def _analyze_and_store_report(self, report_db_id: int, content: str, file_name: str):
        log_props = {"report_db_id": report_db_id, "file_name": file_name, "operation": "analyze_and_store_report"}
        if not content or content.startswith("["):
            logger.info(
                f"報告 ID {report_db_id} ({file_name}) 的內容為空或為錯誤訊息，跳過 AI 分析。",
                extra={"props": {**log_props, "analysis_skipped": True, "reason": "empty_or_error_content"}}
            )
            return
        try:
            logger.info(
                f"開始為報告 ID {report_db_id} ({file_name}) 進行 AI 分析...",
                extra={"props": {**log_props, "ai_analysis_status": "started"}}
            )
            analysis_result = await self.gemini_service.analyze_report(content)

            if analysis_result and not analysis_result.get("錯誤"):
                analysis_json = json.dumps(analysis_result, ensure_ascii=False)
                await self.dal.update_report_analysis(report_db_id, analysis_json, "分析完成")
                logger.info(
                    f"報告 ID {report_db_id} ({file_name}) 的 AI 分析已完成並儲存。",
                    extra={"props": {**log_props, "ai_analysis_status": "success"}}
                )
            else:
                error_message = analysis_result.get("錯誤", "未知分析錯誤") if isinstance(analysis_result, dict) else "未知分析錯誤或服務未配置"
                logger.warning(
                    f"報告 ID {report_db_id} ({file_name}) 的 AI 分析失敗或 Gemini 服務未配置。錯誤: {error_message}",
                    extra={"props": {**log_props, "ai_analysis_status": "failure", "error_detail": error_message, "analysis_result": analysis_result}}
                )
                analysis_error_json = json.dumps({"錯誤": error_message, "原始分析結果": analysis_result}, ensure_ascii=False)
                await self.dal.update_report_analysis(report_db_id, analysis_error_json, "分析失敗")
        except Exception as e:
            logger.error(
                f"為報告 ID {report_db_id} ({file_name}) 執行 AI 分析時發生意外錯誤: {e}",
                exc_info=True, extra={"props": {**log_props, "ai_analysis_status": "exception", "error": str(e)}}
            )
            error_json = json.dumps({"錯誤": f"分析過程中發生意外: {str(e)}"}, ensure_ascii=False)
            await self.dal.update_report_analysis(report_db_id, error_json, "分析失敗(系統異常)")

    async def _archive_file_in_drive(self, file_id: str, file_name: str, processed_folder_id: str, original_parent_folder_id: str) -> Optional[str]:
        log_props = {"file_id": file_id, "file_name": file_name, "processed_folder_id": processed_folder_id, "operation": "archive_file_in_drive"}
        if not self.drive_service:
            logger.error("Drive Service 未初始化，無法執行歸檔操作。", extra={"props": {**log_props, "error": "drive_service_not_initialized"}})
            return "error_drive_service_null"

        logger.info(
            f"準備從來源資料夾 '{original_parent_folder_id}' 刪除原始檔案 '{file_name}' (ID: {file_id})。",
             extra={"props": {**log_props, "archive_step": "delete_original_start", "original_folder_id": original_parent_folder_id}}
        )
        try:
            if hasattr(self.drive_service, 'delete_file'):
                delete_success = await self.drive_service.delete_file(file_id)
                if delete_success:
                    logger.info(f"成功刪除已處理的檔案 '{file_name}'。", extra={"props": {**log_props, "archive_step": "delete_original_success"}})
                    return "deleted_from_inbox"
                else:
                    logger.warning(f"刪除檔案 '{file_name}' 操作未成功。", extra={"props": {**log_props, "archive_step": "delete_original_failed"}})
                    return "delete_from_inbox_failed"
            else:
                logger.warning("`GoogleDriveService` 未找到 `delete_file` 方法。檔案可能未被刪除。", extra={"props": {**log_props, "archive_step": "delete_method_missing"}})
                return "delete_skipped_no_method"
        except Exception as e:
            logger.error(f"歸檔 (刪除) 檔案 '{file_name}' 時發生錯誤: {e}", exc_info=True, extra={"props": {**log_props, "archive_step": "delete_exception", "error": str(e)}})
            return "delete_exception"

    async def ingest_single_drive_file(self, file_id: str, file_name: str, original_parent_folder_id: str, processed_folder_id: str) -> bool:
        """
        處理從 Google Drive 下載的單個報告檔案的完整擷取流程。

        此方法是一個輔助方法，由 `ingest_reports_from_drive_folder` 調用，負責以下步驟：
        1.  **下載**: 使用 `drive_service` 從 Google Drive 下載指定的 `file_id` 到一個本地臨時路徑。
            如果下載失敗，則在資料庫中記錄錯誤狀態並返回 `False`。
        2.  **解析**: 使用 `parsing_service` 從下載的本地檔案中提取純文字內容。
        3.  **初步資料庫記錄**: 使用 `dal` (DataAccessLayer) 將報告的原始檔名、提取的內容（或錯誤訊息）、
            來源路徑 (標記為 `drive_id:{file_id}`) 和初始狀態 ("內容已解析" 或 "擷取錯誤(解析問題)")
            插入到資料庫中。如果插入失敗，記錄錯誤並返回 `False`。
        4.  **AI 分析**: 如果內容成功解析 (狀態為 "內容已解析")，則調用私有方法 `_analyze_and_store_report`
            將內容提交給 `gemini_service` 進行 AI 分析，並將分析結果更新回資料庫。
        5.  **歸檔至 Drive**: 使用 `drive_service` 將本地下載的檔案上傳到指定的 `processed_folder_id`
            (已處理資料夾) 進行歸檔。
        6.  **處理歸檔結果**:
            - 如果歸檔上傳成功，則調用私有方法 `_archive_file_in_drive` 從原始 Drive 資料夾中刪除該檔案。
            - 更新資料庫中報告的狀態為 "已歸檔至Drive" 或 "擷取部分成功(歸檔刪除失敗)" (取決於刪除步驟是否成功)，
              並更新元數據以包含歸檔後的 Drive 檔案 ID 和歸檔狀態詳情。設置最終狀態為 `True`。
            - 如果歸檔上傳失敗，則更新資料庫中報告的狀態為 "擷取錯誤(歸檔上傳失敗)"，並設置最終狀態為 `False`。
        7.  **錯誤處理**: 捕獲在整個過程中發生的任何未預期異常。如果發生異常，嘗試更新資料庫中
            對應報告的狀態為 "擷取錯誤(處理異常)"。如果報告尚未存入資料庫，則嘗試插入一條新的錯誤記錄。
            最終返回 `False`。
        8.  **清理**: 無論成功或失敗，在 `finally` 區塊中嘗試刪除本地下載的臨時檔案。

        Args:
            file_id (str): 要處理的 Google Drive 檔案的 ID。
            file_name (str): Google Drive 檔案的名稱。
            original_parent_folder_id (str): 檔案在 Google Drive 中原始所在的父資料夾 ID。
                                             (主要用於 `_archive_file_in_drive` 確認刪除來源)
            processed_folder_id (str): 用於儲存已處理和歸檔報告的 Google Drive 資料夾的 ID。

        Returns:
            bool: 如果整個擷取、處理和歸檔流程（包括從原始位置成功刪除）均成功，則返回 `True`。
                  在任何關鍵步驟失敗時返回 `False`。
        """
        # 構造本地下載的臨時檔案路徑，確保檔案名中的特殊字元被替換
        local_download_path = os.path.join(TEMP_DOWNLOAD_DIR, f"drive_{file_id}_{file_name.replace('/', '_')}")
        report_db_id = None  # 初始化資料庫中的報告 ID
        content = ""         # 初始化提取的內容
        final_status = False # 初始化最終處理狀態
        log_props_base = {"file_id": file_id, "file_name": file_name, "operation": "ingest_single_drive_file"}

        try:
            logger.info(f"開始處理 Drive 檔案: '{file_name}' (ID: {file_id})。", extra={"props": {**log_props_base, "ingest_step": "start"}})

            # 步驟 1: 下載檔案
            if not self.drive_service: # 檢查 Drive Service 是否已注入
                 logger.error(f"Drive Service 未初始化，無法下載檔案 '{file_name}' (ID: {file_id})。", extra={"props": {**log_props_base, "ingest_step": "error_drive_service_null"}})
                 return False

            download_success = await self.drive_service.download_file(file_id, local_download_path)
            if not download_success:
                logger.error(f"下載 Drive 檔案 '{file_name}' (ID: {file_id}) 失敗。", extra={"props": {**log_props_base, "ingest_step": "download_failed"}})
                # 如果下載失敗，嘗試在資料庫中記錄此錯誤狀態
                await self.dal.insert_report_data(
                    original_filename=file_name, content=None,
                    source_path=f"drive_id:{file_id}",
                    metadata={"error": "download_failed", "drive_file_id": file_id},
                    status="擷取錯誤(下載失敗)"
                )
                return False

            logger.info(f"檔案 '{file_name}' (ID: {file_id}) 下載成功至 '{local_download_path}'。", extra={"props": {**log_props_base, "ingest_step": "download_success", "local_path": local_download_path}})

            # 步驟 2: 解析檔案內容
            # ParsingService 內部會記錄其解析過程的日誌
            content = self.parsing_service.extract_text_from_file(local_download_path)

            # 根據解析結果確定初始資料庫狀態
            initial_status = "內容已解析" if not content.startswith("[") else "擷取錯誤(解析問題)"
            log_props_base["parsed_content_type"] = "valid_text" if initial_status == "內容已解析" else "error_placeholder"

            # 步驟 3: 初步將報告資訊存入資料庫
            # DataAccessLayer 內部會記錄其操作的日誌
            report_db_id = await self.dal.insert_report_data(
                original_filename=file_name, content=content,
                source_path=f"drive_id:{file_id}", # 標明來源為 Drive 檔案
                metadata={"drive_file_id": file_id}, status=initial_status
            )
            log_props_base["report_db_id"] = report_db_id # 更新日誌屬性以便後續使用

            if not report_db_id: # 如果資料庫插入失敗
                logger.error(f"將報告 '{file_name}' (ID: {file_id}) 存入資料庫失敗。", extra={"props": {**log_props_base, "ingest_step": "db_insert_failed"}})
                return False # 關鍵步驟失敗，終止處理

            logger.info(f"報告 '{file_name}' (ID: {file_id}) 已初步存入資料庫，記錄 ID: {report_db_id}，狀態: '{initial_status}'。", extra={"props": {**log_props_base, "ingest_step": "db_insert_success"}})

            # 步驟 4: AI 分析 (如果內容有效)
            if initial_status == "內容已解析":
                # _analyze_and_store_report 方法內部會記錄其詳細日誌
                await self._analyze_and_store_report(report_db_id, content, file_name)

            # 步驟 5: 將處理過的檔案歸檔到 Drive 的指定資料夾
            # drive_service.upload_file 方法內部應記錄其操作日誌
            archived_file_drive_id = await self.drive_service.upload_file(
                local_file_path=local_download_path,
                folder_id=processed_folder_id,
                file_name=file_name # 使用原始檔案名進行歸檔
            )

            # 步驟 6: 處理歸檔結果
            if archived_file_drive_id:
                logger.info(f"檔案 '{file_name}' (ID: {file_id}) 已成功上傳至歸檔資料夾 '{processed_folder_id}' (新 Drive ID: {archived_file_drive_id})。",
                            extra={"props": {**log_props_base, "ingest_step": "archive_upload_success", "archived_drive_id": archived_file_drive_id, "target_folder_id": processed_folder_id}})

                # 從原始位置刪除檔案 (或標記為已處理)
                # _archive_file_in_drive 方法內部記錄其操作日誌
                archive_status_detail = await self._archive_file_in_drive(file_id, file_name, processed_folder_id, original_parent_folder_id)

                # 根據歸檔（主要是刪除原始檔案）的結果，確定報告的最終狀態
                current_report_status_for_archive = "已歸檔至Drive"
                if "failed" in (archive_status_detail or "") or "exception" in (archive_status_detail or ""):
                    current_report_status_for_archive = "擷取部分成功(歸檔刪除失敗)"

                # 僅當報告狀態未被AI分析步驟更新為最終狀態時，才更新為歸檔相關狀態
                current_db_report = await self.dal.get_report_by_id(report_db_id)
                if current_db_report and current_db_report['status'] not in ["分析完成", "分析失敗", "分析失敗(系統異常)"]:
                     await self.dal.update_report_status(report_db_id, current_report_status_for_archive)

                # 更新資料庫中報告的元數據，記錄歸檔後的 Drive ID 和歸檔操作的詳細狀態
                await self.dal.update_report_metadata(report_db_id, {"archived_drive_file_id": archived_file_drive_id, "archive_status": archive_status_detail})
                final_status = True # 表示整個流程基本成功
            else:
                # 如果歸檔上傳失敗
                logger.error(f"歸檔檔案 '{file_name}' (ID: {file_id}) 至 '{processed_folder_id}' 失敗 (上傳步驟)。", extra={"props": {**log_props_base, "ingest_step": "archive_upload_failed"}})
                await self.dal.update_report_status(report_db_id, "擷取錯誤(歸檔上傳失敗)")
                final_status = False # 標記流程失敗

            return final_status # 返回最終處理狀態

        # 步驟 7: 捕獲整個過程中的任何未預期異常
        except Exception as e:
            logger.error(f"處理 Drive 檔案 '{file_name}' (ID: {file_id}) 時發生未預期錯誤: {e}", exc_info=True, extra={"props": {**log_props_base, "ingest_step": "unknown_exception", "error": str(e)}})
            error_status = "擷取錯誤(處理異常)"
            if report_db_id: # 如果報告已存入資料庫，更新其狀態
                await self.dal.update_report_status(report_db_id, error_status)
            else: # 如果報告尚未存入資料庫（例如，在下載或初步插入之前就發生錯誤）
                 # 嘗試插入一條錯誤記錄
                 await self.dal.insert_report_data(
                    original_filename=file_name, content=content if content else "[處理異常，內容未知]",
                    source_path=f"drive_id:{file_id}",
                    metadata={"error": "processing_exception_early", "detail": str(e), "drive_file_id": file_id},
                    status=error_status
                )
            return False # 標記流程失敗

        # 步驟 8: 清理本地下載的臨時檔案
        finally:
            if os.path.exists(local_download_path):
                try:
                    os.remove(local_download_path)
                    logger.info(f"已清理暫存檔案: {local_download_path}", extra={"props": {**log_props_base, "cleanup_step": "temp_file_removed", "local_path": local_download_path}})
                except OSError as e_remove: # 如果刪除臨時檔案失敗
                    logger.error(f"清理暫存檔案 '{local_download_path}' 失敗: {e_remove}", exc_info=True, extra={"props": {**log_props_base, "cleanup_step": "temp_file_remove_failed", "local_path": local_download_path, "error": str(e_remove)}})

    async def ingest_reports_from_drive_folder(self, inbox_folder_id: str, processed_folder_id: str) -> Tuple[int, int]:
        log_props_batch = {"inbox_folder_id": inbox_folder_id, "processed_folder_id": processed_folder_id, "operation": "ingest_reports_from_drive_folder"}
        if not self.drive_service:
            logger.error("Drive Service 未初始化，無法從 Drive 資料夾擷取報告。", extra={"props": {**log_props_batch, "error": "drive_service_not_initialized"}})
            return 0, 0

        logger.info(f"開始從 Drive 資料夾 ID '{inbox_folder_id}' 擷取報告...", extra={"props": {**log_props_batch, "batch_status": "started"}})
        try:
            files = await self.drive_service.list_files_in_folder(inbox_folder_id) # DriveService should log internally
        except Exception as e_list:
            logger.error(f"列出 Drive 資料夾 '{inbox_folder_id}' 中的檔案時發生錯誤: {e_list}", exc_info=True, extra={"props": {**log_props_batch, "batch_status": "list_files_failed", "error": str(e_list)}})
            return 0,0

        if not files:
            logger.info(f"在資料夾 ID '{inbox_folder_id}' 中沒有找到檔案。", extra={"props": {**log_props_batch, "batch_status": "no_files_found"}})
            return 0, 0

        success_count = 0
        fail_count = 0

        for file_item in files:
            file_id = file_item.get('id')
            file_name = file_item.get('name')
            log_props_item = {**log_props_batch, "current_file_id": file_id, "current_file_name": file_name}

            if not file_id or not file_name:
                logger.warning(f"從 Drive API 收到的檔案項目缺少 ID 或名稱: {file_item}，跳過此項目。", extra={"props": {**log_props_item, "error": "missing_file_id_or_name", "file_item": file_item}})
                fail_count +=1
                continue

            logger.info(f"準備處理 Drive 檔案 '{file_name}' (ID: {file_id})...", extra={"props": log_props_item})
            try:
                if await self.dal.check_report_exists_by_source_path(f"drive_id:{file_id}"): # DAL logs internally
                    logger.info(f"報告來源 '{file_name}' (Drive ID: {file_id}) 已存在於資料庫中，跳過重複擷取。", extra={"props": {**log_props_item, "skipped": "duplicate_by_source_path"}})
                    continue

                if await self.ingest_single_drive_file(file_id, file_name, inbox_folder_id, processed_folder_id): # This method logs extensively
                    success_count += 1
                    # logger.info(f"成功處理並歸檔 Drive 檔案 '{file_name}' (ID: {file_id})。", extra={"props": {**log_props_item, "ingest_status": "success"}}) # Redundant if ingest_single_drive_file logs its final success
                else:
                    fail_count += 1
                    logger.warning(f"處理 Drive 檔案 '{file_name}' (ID: {file_id}) 未完全成功 (詳見先前日誌)。", extra={"props": {**log_props_item, "ingest_status": "failed"}})
            except Exception as e_single_file:
                fail_count += 1
                logger.error(f"於排程任務中處理 Drive 檔案 '{file_name}' (ID: {file_id}) 時發生頂層錯誤: {e_single_file}", exc_info=True, extra={"props": {**log_props_item, "ingest_status": "loop_exception", "error": str(e_single_file)}})
                if not await self.dal.check_report_exists_by_source_path(f"drive_id:{file_id}"):
                    try:
                        await self.dal.insert_report_data(
                            original_filename=file_name, content=f"[排程處理時發生錯誤: {str(e_single_file)}]",
                            source_path=f"drive_id:{file_id}",
                            metadata={"error": "scheduler_loop_exception", "drive_file_id": file_id},
                            status="擷取錯誤(排程異常)"
                        )
                    except Exception as db_e:
                        logger.error(f"為錯誤檔案 '{file_name}' (ID: {file_id}) 寫入錯誤記錄到資料庫時再次失敗: {db_e}", exc_info=True, extra={"props": {**log_props_item, "db_error_logging_failed": str(db_e)}})

        logger.info(f"從 Drive 資料夾 '{inbox_folder_id}' 擷取完成。成功: {success_count} 個, 失敗: {fail_count} 個。", extra={"props": {**log_props_batch, "batch_status": "completed", "success_count": success_count, "fail_count": fail_count}})
        return success_count, fail_count

    async def ingest_uploaded_file(self, file_name: str, file_path: str) -> Optional[int]:
        """
        處理使用者直接上傳的報告檔案。

        此方法負責處理通過應用程式接口直接上傳的檔案。與從 Google Drive 擷取的檔案不同，
        這些檔案通常已經存在於本地檔案系統的某個臨時位置。其工作流程如下：

        1.  **解析內容**: 使用 `parsing_service` 從指定的 `file_path` 提取純文字內容。
            `ParsingService` 內部會處理不同檔案類型的解析邏輯和相關錯誤。
        2.  **確定初始狀態**: 根據 `parsing_service` 返回的內容判斷解析是否成功。
            如果內容以 "[" 開頭，通常表示 `ParsingService` 返回了一個錯誤或提示訊息
            (例如，"[檔案未找到...]" 或 "[不支援的檔案類型...]")，此時將初始狀態
            設置為 "擷取錯誤(解析問題)"；否則，設置為 "內容已解析"。
        3.  **存入資料庫**: 調用 `dal.insert_report_data` 將報告資訊存入資料庫。
            儲存的資訊包括：原始檔名 (`file_name`)、提取的內容、來源路徑 (標記為 `upload:{file_name}`)、
            上傳時間戳，以及確定的初始狀態。
        4.  **處理資料庫插入結果**: 如果資料庫插入失敗 (`report_db_id` 為 None)，記錄錯誤並返回 `None`。
        5.  **AI 分析**: 如果內容成功解析 (即 `initial_status` 為 "內容已解析")，
            則調用私有輔助方法 `_analyze_and_store_report`，將內容提交給 `gemini_service`
            進行 AI 分析，並將結果更新回資料庫中對應的報告記錄。
        6.  **返回報告 ID**: 如果一切順利（至少資料庫初步插入成功），返回在資料庫中創建的報告記錄 ID。
        7.  **錯誤處理**: 捕獲在整個過程中發生的任何未預期異常。如果發生異常：
            - 若報告已成功存入資料庫 (`report_db_id` 已存在)，則嘗試更新該報告的分析結果
              為一個包含錯誤信息的 JSON，並將狀態更新為 "擷取錯誤(系統異常)"。
            - 返回 `None`。

        注意：此方法不涉及 Google Drive 的歸檔操作，因為檔案是直接上傳的，
        其生命週期管理可能由應用程式的其他部分或調用者負責。

        Args:
            file_name (str): 使用者上傳時提供的原始檔案名稱。
            file_path (str): 檔案在伺服器上儲存的臨時路徑或可訪問路徑。
                             `ParsingService` 將從此路徑讀取檔案。

        Returns:
            Optional[int]: 如果報告成功存入資料庫（即使後續 AI 分析可能失敗），
                           則返回該報告在資料庫中的唯一 ID。
                           如果在關鍵步驟（如資料庫初步插入）失敗，或發生未捕獲的頂層異常，
                           則返回 `None`。
        """
        log_props_upload = {"file_name": file_name, "file_path": file_path, "operation": "ingest_uploaded_file"}
        logger.info(f"開始處理上傳的檔案: '{file_name}'，路徑: '{file_path}'。", extra={"props": {**log_props_upload, "upload_step": "start"}})
        report_db_id = None # 初始化資料庫報告 ID
        try:
            # 步驟 1: 解析檔案內容
            # ParsingService 內部會記錄其詳細的解析日誌
            content = self.parsing_service.extract_text_from_file(file_path)

            # 步驟 2: 根據解析結果確定初始狀態
            # ParsingService 在無法解析或檔案不受支持時會返回以 '[' 開頭的錯誤或提示訊息
            initial_status = "內容已解析" if not content.startswith("[") else "擷取錯誤(解析問題)"
            log_props_upload["parsed_content_type"] = "valid_text" if initial_status == "內容已解析" else "error_placeholder"

            # 步驟 3: 將報告資訊（包括內容和初始狀態）存入資料庫
            # DataAccessLayer 內部會記錄其操作的日誌
            report_db_id = await self.dal.insert_report_data(
                original_filename=file_name,
                content=content,
                source_path=f"upload:{file_name}", # 標記來源為直接上傳
                metadata={"upload_timestamp": datetime.utcnow().isoformat()}, # 記錄上傳時間戳
                status=initial_status
            )
            log_props_upload["report_db_id"] = report_db_id # 更新日誌屬性

            # 步驟 4: 處理資料庫插入結果
            if not report_db_id: # 如果未能獲取到資料庫 ID，表示插入失敗
                logger.error(f"處理上傳的檔案 '{file_name}' 後，存入資料庫失敗。", extra={"props": {**log_props_upload, "upload_step": "db_insert_failed"}})
                return None # 返回 None 表示處理失敗

            logger.info(f"上傳的檔案 '{file_name}' 已成功處理並存入資料庫，ID: {report_db_id}，狀態: '{initial_status}'。", extra={"props": {**log_props_upload, "upload_step": "db_insert_success"}})

            # 步驟 5: 如果內容已成功解析，則進行 AI 分析
            if initial_status == "內容已解析":
                # _analyze_and_store_report 方法內部會記錄其詳細日誌
                await self._analyze_and_store_report(report_db_id, content, file_name)

            # 步驟 6: 返回成功存入資料庫的報告 ID
            return report_db_id

        # 步驟 7: 捕獲處理過程中的任何未預期異常
        except Exception as e:
            logger.error(f"處理上傳的檔案 '{file_name}' 時發生錯誤: {e}", exc_info=True, extra={"props": {**log_props_upload, "upload_step": "exception", "error": str(e)}})
            if report_db_id: # 如果報告已存入資料庫，但後續步驟（如AI分析）出錯
                # 更新資料庫中的分析結果為錯誤信息，並將狀態標記為系統異常
                error_json = json.dumps({"錯誤": f"處理上傳檔案時發生意外: {str(e)}"}, ensure_ascii=False)
                await self.dal.update_report_analysis(report_db_id, error_json, "擷取錯誤(系統異常)")
            return None # 返回 None 表示處理失敗
