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
        local_download_path = os.path.join(TEMP_DOWNLOAD_DIR, f"drive_{file_id}_{file_name.replace('/', '_')}")
        report_db_id = None
        content = ""
        final_status = False
        log_props_base = {"file_id": file_id, "file_name": file_name, "operation": "ingest_single_drive_file"}

        try:
            logger.info(f"開始處理 Drive 檔案: '{file_name}' (ID: {file_id})。", extra={"props": {**log_props_base, "ingest_step": "start"}})
            if not self.drive_service:
                 logger.error(f"Drive Service 未初始化，無法下載檔案 '{file_name}' (ID: {file_id})。", extra={"props": {**log_props_base, "ingest_step": "error_drive_service_null"}})
                 return False

            download_success = await self.drive_service.download_file(file_id, local_download_path)
            if not download_success:
                logger.error(f"下載 Drive 檔案 '{file_name}' (ID: {file_id}) 失敗。", extra={"props": {**log_props_base, "ingest_step": "download_failed"}})
                # DAL call already logs its own success/failure.
                await self.dal.insert_report_data(
                    original_filename=file_name, content=None,
                    source_path=f"drive_id:{file_id}",
                    metadata={"error": "download_failed", "drive_file_id": file_id},
                    status="擷取錯誤(下載失敗)"
                )
                return False

            logger.info(f"檔案 '{file_name}' (ID: {file_id}) 下載成功至 '{local_download_path}'。", extra={"props": {**log_props_base, "ingest_step": "download_success", "local_path": local_download_path}})

            content = self.parsing_service.extract_text_from_file(local_download_path) # ParsingService logs internally

            initial_status = "內容已解析" if not content.startswith("[") else "擷取錯誤(解析問題)"
            log_props_base["parsed_content_type"] = "valid_text" if initial_status == "內容已解析" else "error_placeholder"

            report_db_id = await self.dal.insert_report_data(
                original_filename=file_name, content=content,
                source_path=f"drive_id:{file_id}",
                metadata={"drive_file_id": file_id}, status=initial_status
            ) # DAL logs internally
            log_props_base["report_db_id"] = report_db_id

            if not report_db_id:
                logger.error(f"將報告 '{file_name}' (ID: {file_id}) 存入資料庫失敗。", extra={"props": {**log_props_base, "ingest_step": "db_insert_failed"}})
                return False

            logger.info(f"報告 '{file_name}' (ID: {file_id}) 已初步存入資料庫，記錄 ID: {report_db_id}，狀態: '{initial_status}'。", extra={"props": {**log_props_base, "ingest_step": "db_insert_success"}})

            if initial_status == "內容已解析":
                await self._analyze_and_store_report(report_db_id, content, file_name) # This method logs internally

            archived_file_drive_id = await self.drive_service.upload_file(
                local_file_path=local_download_path,
                folder_id=processed_folder_id,
                file_name=file_name
            ) # DriveService upload_file should log internally

            if archived_file_drive_id:
                logger.info(f"檔案 '{file_name}' (ID: {file_id}) 已成功上傳至歸檔資料夾 '{processed_folder_id}' (新 Drive ID: {archived_file_drive_id})。",
                            extra={"props": {**log_props_base, "ingest_step": "archive_upload_success", "archived_drive_id": archived_file_drive_id, "target_folder_id": processed_folder_id}})
                archive_status_detail = await self._archive_file_in_drive(file_id, file_name, processed_folder_id, original_parent_folder_id) # This method logs internally

                current_report_status_for_archive = "已歸檔至Drive"
                if "failed" in (archive_status_detail or "") or "exception" in (archive_status_detail or ""):
                    current_report_status_for_archive = "擷取部分成功(歸檔刪除失敗)"

                current_db_report = await self.dal.get_report_by_id(report_db_id)
                if current_db_report and current_db_report['status'] not in ["分析完成", "分析失敗", "分析失敗(系統異常)"]:
                     await self.dal.update_report_status(report_db_id, current_report_status_for_archive)

                await self.dal.update_report_metadata(report_db_id, {"archived_drive_file_id": archived_file_drive_id, "archive_status": archive_status_detail})
                final_status = True
            else:
                logger.error(f"歸檔檔案 '{file_name}' (ID: {file_id}) 至 '{processed_folder_id}' 失敗 (上傳步驟)。", extra={"props": {**log_props_base, "ingest_step": "archive_upload_failed"}})
                await self.dal.update_report_status(report_db_id, "擷取錯誤(歸檔上傳失敗)")
                final_status = False

            return final_status

        except Exception as e:
            logger.error(f"處理 Drive 檔案 '{file_name}' (ID: {file_id}) 時發生未預期錯誤: {e}", exc_info=True, extra={"props": {**log_props_base, "ingest_step": "unknown_exception", "error": str(e)}})
            error_status = "擷取錯誤(處理異常)"
            if report_db_id:
                await self.dal.update_report_status(report_db_id, error_status)
            else:
                 await self.dal.insert_report_data(
                    original_filename=file_name, content=content if content else "[處理異常，內容未知]",
                    source_path=f"drive_id:{file_id}",
                    metadata={"error": "processing_exception_early", "detail": str(e), "drive_file_id": file_id},
                    status=error_status
                )
            return False
        finally:
            if os.path.exists(local_download_path):
                try:
                    os.remove(local_download_path)
                    logger.info(f"已清理暫存檔案: {local_download_path}", extra={"props": {**log_props_base, "cleanup_step": "temp_file_removed", "local_path": local_download_path}})
                except OSError as e_remove:
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
        log_props_upload = {"file_name": file_name, "file_path": file_path, "operation": "ingest_uploaded_file"}
        logger.info(f"開始處理上傳的檔案: '{file_name}'，路徑: '{file_path}'。", extra={"props": {**log_props_upload, "upload_step": "start"}})
        report_db_id = None
        try:
            content = self.parsing_service.extract_text_from_file(file_path) # ParsingService logs internally
            initial_status = "內容已解析" if not content.startswith("[") else "擷取錯誤(解析問題)"
            log_props_upload["parsed_content_type"] = "valid_text" if initial_status == "內容已解析" else "error_placeholder"

            report_db_id = await self.dal.insert_report_data(
                original_filename=file_name, content=content,
                source_path=f"upload:{file_name}",
                metadata={"upload_timestamp": datetime.utcnow().isoformat()}, status=initial_status
            ) # DAL logs internally
            log_props_upload["report_db_id"] = report_db_id

            if not report_db_id:
                logger.error(f"處理上傳的檔案 '{file_name}' 後，存入資料庫失敗。", extra={"props": {**log_props_upload, "upload_step": "db_insert_failed"}})
                return None

            logger.info(f"上傳的檔案 '{file_name}' 已成功處理並存入資料庫，ID: {report_db_id}，狀態: '{initial_status}'。", extra={"props": {**log_props_upload, "upload_step": "db_insert_success"}})

            if initial_status == "內容已解析":
                await self._analyze_and_store_report(report_db_id, content, file_name) # This method logs internally

            return report_db_id
        except Exception as e:
            logger.error(f"處理上傳的檔案 '{file_name}' 時發生錯誤: {e}", exc_info=True, extra={"props": {**log_props_upload, "upload_step": "exception", "error": str(e)}})
            if report_db_id:
                error_json = json.dumps({"錯誤": f"處理上傳檔案時發生意外: {str(e)}"}, ensure_ascii=False)
                await self.dal.update_report_analysis(report_db_id, error_json, "擷取錯誤(系統異常)")
            return None
