import os
import logging
import shutil # 用於檔案操作，例如刪除暫存檔案
from datetime import datetime
from typing import TYPE_CHECKING, Tuple, Optional, List

if TYPE_CHECKING:
    from .google_drive_service import GoogleDriveService
    from .data_access_layer import DataAccessLayer

# 配置日誌記錄器
# logging.basicConfig(level=logging.INFO) # 通常在主應用 (main.py) 中統一配置
logger = logging.getLogger(__name__)

# 定義暫存下載檔案的目錄路徑
# SERVICE_DIR 指向當前檔案 (report_ingestion_service.py) 所在的目錄 (services/)
SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
# BACKEND_DIR 指向 backend/ 目錄
BACKEND_DIR = os.path.dirname(SERVICE_DIR)
# TEMP_DOWNLOAD_DIR 指向 backend/data/temp_downloads/
TEMP_DOWNLOAD_DIR = os.path.join(BACKEND_DIR, 'data', 'temp_downloads')

# 啟動時確保暫存下載目錄存在
os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)
logger.info(f"報告擷取服務：暫存下載目錄設定於 '{TEMP_DOWNLOAD_DIR}'。")

class ReportIngestionService:
    def __init__(self, drive_service: 'GoogleDriveService', dal: 'DataAccessLayer'):
        """
        初始化報告擷取服務。
        :param drive_service: GoogleDriveService 的實例，用於與 Google Drive 互動。
        :param dal: DataAccessLayer 的實例，用於資料庫操作。
        """
        self.drive_service = drive_service
        self.dal = dal
        logger.info("報告擷取服務 (ReportIngestionService) 已初始化。")

    def _get_file_extension(self, file_name: str) -> str: # 輔助函數：獲取檔案的副檔名 (小寫)。
        return os.path.splitext(file_name)[1].lower()

    async def _parse_report_content(self, local_file_path: str) -> str:
# 配置日誌記錄器
# logging.basicConfig(level=logging.INFO) # 通常在主應用 (main.py) 中統一配置
logger = logging.getLogger(__name__)

# 定義暫存下載檔案的目錄路徑
# SERVICE_DIR 指向當前檔案 (report_ingestion_service.py) 所在的目錄 (services/)
SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
# BACKEND_DIR 指向 backend/ 目錄
BACKEND_DIR = os.path.dirname(SERVICE_DIR)
# TEMP_DOWNLOAD_DIR 指向 backend/data/temp_downloads/
TEMP_DOWNLOAD_DIR = os.path.join(BACKEND_DIR, 'data', 'temp_downloads')

# 啟動時確保暫存下載目錄存在
os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)
logger.info(f"報告擷取服務：暫存下載目錄設定於 '{TEMP_DOWNLOAD_DIR}'。")

class ReportIngestionService:
    def __init__(self, drive_service: 'GoogleDriveService', dal: 'DataAccessLayer'):
        """
        初始化報告擷取服務。
        :param drive_service: GoogleDriveService 的實例，用於與 Google Drive 互動。
        :param dal: DataAccessLayer 的實例，用於資料庫操作。
        """
        self.drive_service = drive_service
        self.dal = dal
        logger.info("報告擷取服務 (ReportIngestionService) 已初始化。")

    def _get_file_extension(self, file_name: str) -> str: # 輔助函數：獲取檔案的副檔名 (小寫)。
        return os.path.splitext(file_name)[1].lower()

    async def _parse_report_content(self, local_file_path: str) -> str:
        """
        異步解析本地報告檔案的內容。
        目前主要支援 .txt 和 .md 純文字檔案。其他格式會記錄警告並返回預設內容。
        :param local_file_path: 本地檔案的路徑。
        :return: 解析出的檔案內容字串。
        """
        file_extension = self._get_file_extension(local_file_path)
        content = ""
        logger.info(f"開始解析檔案 '{local_file_path}' (類型: {file_extension})...")
        try:
            if file_extension == ".txt":
                with open(local_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                logger.info(f"成功解析純文字檔案 (.txt): {local_file_path}")
            elif file_extension == ".md": # Markdown 也視為純文字處理
                with open(local_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                logger.info(f"成功解析 Markdown 檔案 (.md): {local_file_path}")
            # TODO (未來擴展): 添加對 .docx, .pdf 等複雜格式的解析邏輯。
            # 例如，可以使用 python-docx 處理 .docx，pypdf 或其他 PDF 解析庫處理 .pdf。
            elif file_extension == ".docx":
                logger.warning(f"注意：.docx 檔案 ({local_file_path}) 的內容解析功能目前尚未完整實現。將返回預設提示。")
                content = "[.docx 檔案內容解析功能待實現]"
            elif file_extension == ".pdf":
                logger.warning(f"注意：.pdf 檔案 ({local_file_path}) 的內容解析功能目前尚未完整實現。將返回預設提示。")
                content = "[.pdf 檔案內容解析功能待實現]"
            else:
                logger.warning(f"不支援的檔案類型 '{file_extension}' ({local_file_path})。無法進行內容解析。")
                content = f"[不支援的檔案類型進行內容解析: {file_extension}]"
        except Exception as e:
            logger.error(f"解析檔案 '{local_file_path}' 過程中發生錯誤: {e}", exc_info=True)
            content = f"[檔案內容解析時發生錯誤: {str(e)}]"
        return content

    async def _archive_file_in_drive(self, file_id: str, file_name: str, processed_folder_id: str, original_parent_folder_id: str) -> Optional[str]:
        """
        將已處理的 Google Drive 檔案歸檔 (移動到 'processed' 資料夾)。
        此為一個概念性函數，實際的移動操作依賴 GoogleDriveService 的 `move_file` 或 `delete_file` 方法。
        目前的實現策略是：在 `ingest_single_drive_file` 中，已將檔案副本上傳到 `processed_folder_id`。
        此函數的未來職責是刪除 `original_parent_folder_id` (即 inbox) 中的原始檔案。

        :param file_id: 要歸檔的原始檔案 ID。
        :param file_name: 檔案名稱 (用於日誌)。
        :param processed_folder_id: "已處理" 資料夾的 ID (用於日誌，實際移動已發生)。
        :param original_parent_folder_id: 原始檔案所在的父資料夾 ID (即 inbox ID)。
        :return: 操作狀態的描述字串，或 None (如果未執行任何操作)。
        """
        # 在當前 ingest_single_drive_file 的流程中，檔案的副本已經被上傳到了 processed_folder_id。
        # 所以這裡的 "歸檔" 主要是指從原始的 inbox 資料夾中移除該檔案。
        logger.info(f"準備歸檔檔案 '{file_name}' (ID: {file_id})。")
        logger.warning(f"歸檔操作：從來源資料夾 '{original_parent_folder_id}' 刪除原始檔案 '{file_name}' (ID: {file_id}) 的功能，依賴 `GoogleDriveService.delete_file()`。")

        try:
            # 假設 GoogleDriveService 提供了 delete_file 方法
            if hasattr(self.drive_service, 'delete_file') and callable(getattr(self.drive_service, 'delete_file')):
                delete_success = await self.drive_service.delete_file(file_id)
                if delete_success:
                    logger.info(f"成功：已從來源資料夾 '{original_parent_folder_id}' 刪除已處理的檔案 '{file_name}' (ID: {file_id})。")
                    return "deleted_from_inbox"
                else:
                    logger.warning(f"歸檔失敗：從來源資料夾 '{original_parent_folder_id}' 刪除檔案 '{file_name}' (ID: {file_id}) 操作未成功。")
                    return "delete_from_inbox_failed"
            else:
                logger.warning("`GoogleDriveService` 中未找到 `delete_file` 方法。跳過從收件箱刪除原始檔案的步驟。")
                return "delete_skipped_no_method"
        except Exception as e:
            logger.error(f"歸檔 (刪除) 檔案 '{file_name}' (ID: {file_id}) 時發生錯誤: {e}", exc_info=True)
            return "delete_exception"


    async def ingest_single_drive_file(self, file_id: str, file_name: str, original_parent_folder_id: str, processed_folder_id: str) -> bool:
        """
        處理單個在 Google Drive 中的檔案：下載、解析、存入資料庫、上傳副本到已處理資料夾，並嘗試刪除原檔案。
        :param file_id: Drive 中檔案的 ID。
        :param file_name: Drive 中檔案的名稱。
        :param original_parent_folder_id: 檔案目前所在的父資料夾 ID (例如 "wolf_in" 資料夾)。
        :param processed_folder_id: 處理完成後，檔案副本應歸檔到的資料夾 ID (例如 "wolf_in/processed" 資料夾)。
        :return: 如果整個流程成功完成則返回 True，否則返回 False。
        """
        # 確保 TEMP_DOWNLOAD_DIR 存在
        os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)
        # 構造一個唯一的本地暫存檔案路徑，避免因檔名重複導致衝突
        local_download_path = os.path.join(TEMP_DOWNLOAD_DIR, f"drive_{file_id}_{file_name}")

        processed_successfully = False
        report_db_id = None # 初始化資料庫中的報告 ID
        content = None      # 初始化內容變數

        try:
            logger.info(f"開始處理 Drive 檔案: '{file_name}' (ID: {file_id}) (來源資料夾 ID: '{original_parent_folder_id}')。")

            # 步驟 1: 從 Google Drive 下載檔案到本地暫存區
            download_success = await self.drive_service.download_file(file_id, local_download_path)
            if not download_success:
                logger.error(f"下載 Drive 檔案 '{file_name}' (ID: {file_id}) 失敗。")
                # 記錄下載失敗到資料庫
                report_db_id = await self.dal.insert_report_data(
                    original_filename=file_name,
                    content=None, # 因為下載失敗，沒有內容
                    source_path=f"drive_id:{file_id}", # 記錄原始 Drive ID
                    metadata={"error_type": "download_failed", "drive_file_id": file_id, "original_folder_id": original_parent_folder_id},
                    status="擷取錯誤(下載失敗)" # 中文狀態
                )
                return False # 中斷後續處理

            # 步驟 2: 解析已下載檔案的內容
            logger.info(f"檔案 '{file_name}' 已成功下載到 '{local_download_path}'，準備進行內容解析。")
            content = await self._parse_report_content(local_download_path)

            # 步驟 3: 將報告資訊 (包括解析後的內容) 寫入資料庫
            # 無論內容解析是否完美，都先記錄一筆資料
            report_db_id = await self.dal.insert_report_data(
                original_filename=file_name,
                content=content,
                source_path=f"drive_id:{file_id}",
                metadata={"drive_file_id": file_id, "original_folder_id": original_parent_folder_id, "parsed_extension": self._get_file_extension(file_name)},
                status="已擷取待處理" # 初始狀態
            )

            if not report_db_id:
                logger.error(f"將報告 '{file_name}' (Drive ID: {file_id}) 的元數據和內容存入資料庫失敗。")
                # 即使資料庫存儲失敗，也應嘗試歸檔 Drive 上的檔案，以避免重複處理有問題的檔案
            else:
                logger.info(f"報告 '{file_name}' (Drive ID: {file_id}) 已成功存入資料庫，記錄 ID 為: {report_db_id}。")
                # 可以選擇在此處更新資料庫狀態為“已解析”或類似狀態
                await self.dal.update_report_status(report_db_id, "內容已解析", processed_content=content)


            # 步驟 4: 將本地下載的檔案副本上傳到 Drive 的 "已處理" (processed) 資料夾
            # 這一步驟實現了 "歸檔" 的一部分：將處理過的檔案副本存放到指定位置
            logger.info(f"準備將 '{file_name}' 的副本上傳到 Drive 的 '已處理' 資料夾 (ID: '{processed_folder_id}')。")
            archived_file_id = await self.drive_service.upload_file(
                local_file_path=local_download_path,
                folder_id=processed_folder_id,
                file_name=file_name # 在 "已處理" 資料夾中保留原始檔案名
            )

            if archived_file_id:
                logger.info(f"檔案 '{file_name}' 的副本已成功歸檔到 Drive '已處理' 資料夾 (ID: '{processed_folder_id}')。新歸檔檔案 ID: {archived_file_id}.")
                # 步驟 4.1 (可選但推薦): 從原始的 'inbox' 資料夾中刪除原檔案，完成歸檔閉環
                archive_delete_status = await self._archive_file_in_drive(file_id, file_name, processed_folder_id, original_parent_folder_id)
                logger.info(f"原始檔案 '{file_name}' (ID: {file_id}) 在收件箱中的歸檔 (刪除) 操作狀態: {archive_delete_status}")

                if report_db_id: # 如果資料庫記錄存在，更新其狀態為“已歸檔”
                    await self.dal.update_report_status(report_db_id, "已歸檔至Drive", processed_content=content) # 使用中文狀態
                processed_successfully = True
            else:
                logger.error(f"歸檔檔案 '{file_name}' (原始 Drive ID: {file_id}) 到 '已處理' 資料夾 (ID: '{processed_folder_id}') 失敗。")
                if report_db_id: # 如果資料庫記錄存在，更新其狀態為歸檔錯誤
                    await self.dal.update_report_status(report_db_id, "擷取錯誤(歸檔失敗)", processed_content=content) # 使用中文狀態
                processed_successfully = False

        except Exception as e:
            logger.error(f"處理 Drive 檔案 '{file_name}' (ID: {file_id}) 過程中發生未預期錯誤: {e}", exc_info=True)
            final_status_on_error = "擷取錯誤(處理異常)" # 中文狀態
            if report_db_id: # 如果在異常發生前已創建資料庫記錄
                 await self.dal.update_report_status(report_db_id, final_status_on_error, processed_content=content)
            elif file_id: # 如果連資料庫記錄都沒來得及創建
                 await self.dal.insert_report_data( # 嘗試記錄此錯誤
                    original_filename=file_name,
                    content=None,
                    source_path=f"drive_id:{file_id}",
                    metadata={"error_type": f"processing_exception: {str(e)}", "drive_file_id": file_id, "original_folder_id": original_parent_folder_id},
                    status=final_status_on_error
                )
            processed_successfully = False
        finally:
            # 步驟 5: 清理本地的暫存檔案
            if os.path.exists(local_download_path):
                try:
                    os.remove(local_download_path)
                    logger.info(f"已成功刪除本地暫存檔案: {local_download_path}")
                except Exception as e_remove:
                    logger.error(f"刪除本地暫存檔案 '{local_download_path}' 時發生錯誤: {e_remove}")

        logger.info(f"Drive 檔案 '{file_name}' (ID: {file_id}) 處理完成。最終成功狀態: {processed_successfully}。")
        return processed_successfully

    async def ingest_reports_from_drive_folder(self, inbox_folder_id: str, processed_folder_id: str) -> Tuple[int, int]:
        """
        從指定的 Drive 資料夾 (例如 "wolf_in") 擷取所有報告檔案進行處理。
        :param inbox_folder_id: Drive 中存放待處理報告的入口資料夾 ID。
        :param processed_folder_id: Drive 中用於存放已成功處理報告的歸檔資料夾 ID。
        :return: 一個元組 (成功處理的檔案數量, 處理失敗的檔案數量)。
        """
        logger.info(f"開始從 Drive 收件箱資料夾 (ID: '{inbox_folder_id}') 擷取報告。已處理檔案將歸檔至資料夾 ID: '{processed_folder_id}'。")
        successful_ingestions = 0
        failed_ingestions = 0
        files_in_inbox: List[dict] = [] # 確保在異常情況下 files_in_inbox 已定義

        try:
            # 步驟 1: 列出 'inbox_folder_id' (例如 "wolf_in") 中的所有項目
            files_in_inbox = await self.drive_service.list_files(folder_id=inbox_folder_id)
            if not files_in_inbox:
                logger.info(f"指定的 Drive 收件箱資料夾 (ID: '{inbox_folder_id}') 中目前沒有找到任何檔案。擷取結束。")
                return 0, 0

            logger.info(f"在 Drive 收件箱資料夾 (ID: '{inbox_folder_id}') 中找到 {len(files_in_inbox)} 個項目。開始逐個處理...")

            for drive_file in files_in_inbox:
                file_id = drive_file.get('id')
                file_name = drive_file.get('name')
                mime_type = drive_file.get('mimeType')

                if not file_id or not file_name: # 檢查是否有無效的 Drive 項目資訊
                    logger.warning(f"檢測到一個無效的 Drive 項目，缺少 ID 或名稱: {drive_file}。跳過此項目。")
                    failed_ingestions +=1
                    continue

                # 避免處理 Google Drive 中的資料夾本身 (如果擷取邏輯不包含遞歸處理)
                if mime_type == 'application/vnd.google-apps.folder':
                    logger.info(f"項目 '{file_name}' (ID: {file_id}) 是一個資料夾，將跳過。本擷取服務目前不遞歸處理子資料夾。")
                    continue # 跳過資料夾，繼續處理下一個項目

                logger.info(f"準備處理 Drive 收件箱中的檔案: '{file_name}' (ID: {file_id}, 類型: {mime_type})")

                # 處理單個檔案
                if await self.ingest_single_drive_file(file_id, file_name, inbox_folder_id, processed_folder_id):
                    successful_ingestions += 1
                else:
                    failed_ingestions += 1
                logger.info(f"檔案 '{file_name}' (ID: {file_id}) 處理完畢。目前成功: {successful_ingestions}, 失敗: {failed_ingestions}。")


        except Exception as e:
            logger.error(f"從 Drive 收件箱資料夾 (ID: '{inbox_folder_id}') 擷取報告過程中發生嚴重錯誤: {e}", exc_info=True)
            # 如果在列出檔案或迴圈早期發生錯誤，剩餘未處理的檔案也應計為失敗
            # （這是一個簡化的計算，實際可能需要更細緻的錯誤追蹤）
            processed_count_before_error = successful_ingestions + failed_ingestions
            remaining_files_unattempted = len(files_in_inbox) - processed_count_before_error
            if remaining_files_unattempted > 0:
                 logger.warning(f"由於發生嚴重錯誤，有 {remaining_files_unattempted} 個檔案可能未被嘗試處理，將計為失敗。")
                 failed_ingestions += remaining_files_unattempted
            return successful_ingestions, failed_ingestions # 返回當前統計的成功和失敗數量

        logger.info(f"所有 Drive 收件箱 (ID: '{inbox_folder_id}') 中的項目處理完成。總計成功: {successful_ingestions} 個檔案，失敗: {failed_ingestions} 個檔案。")
        return successful_ingestions, failed_ingestions

    async def ingest_uploaded_file(
        self,
        local_temp_file_path: str, # 後端接收到的上傳檔案的本地暫存路徑
        original_filename: str,    # 使用者上傳時提供的原始檔案名
        drive_inbox_folder_id: str, # Drive 中的 "wolf_in" (收件箱) 資料夾 ID
        drive_processed_folder_id: str # Drive 中的 "wolf_in/processed" (已處理) 資料夾 ID
    ) -> bool:
        """
        處理由前端介面上傳的單個檔案。
        主要流程：
        1. 將本地暫存的已上傳檔案，先上傳到 Google Drive 的指定 '收件箱' (wolf_in) 資料夾。
        2. 一旦檔案成功上傳到 Drive 收件箱，就觸發對該 Drive 檔案的標準擷取流程 (即調用 ingest_single_drive_file)。
        :param local_temp_file_path: 檔案在後端伺服器上的本地臨時路徑。
        :param original_filename: 使用者上傳時指定的檔案名稱。
        :param drive_inbox_folder_id: Google Drive 中用於接收新檔案的 "收件箱" 資料夾 ID。
        :param drive_processed_folder_id: Google Drive 中用於存放已處理檔案的 "已處理" 資料夾 ID。
        :return: 如果整個上傳和後續擷取流程均成功，則返回 True，否則返回 False。
        """
        logger.info(f"開始處理使用者上傳的檔案: '{original_filename}' (本地暫存路徑: '{local_temp_file_path}')")

        try:
            # 步驟 1: 將本地暫存的檔案上傳到 Drive 的 'wolf_in' (收件箱) 資料夾
            logger.info(f"準備將檔案 '{original_filename}' 上傳到 Drive 收件箱 (ID: '{drive_inbox_folder_id}')。")
            uploaded_drive_file_id = await self.drive_service.upload_file(
                local_file_path=local_temp_file_path,
                folder_id=drive_inbox_folder_id,
                file_name=original_filename # 在 Drive 中使用原始檔案名
            )

            if not uploaded_drive_file_id:
                logger.error(f"將上傳的檔案 '{original_filename}' 轉存到 Drive 收件箱資料夾 (ID: '{drive_inbox_folder_id}') 失敗。")
                # 記錄到資料庫，標記為上傳到 Drive 失敗
                await self.dal.insert_report_data(
                    original_filename=original_filename,
                    content=None,
                    source_path=f"upload_failed_to_drive_inbox:{original_filename}", # 特殊來源路徑標記
                    metadata={"error_description": "Failed to upload the user's file to the Drive inbox folder."},
                    status="錯誤(轉存Drive收件箱失敗)" # 中文狀態
                )
                return False # 中斷處理

            logger.info(f"使用者上傳的檔案 '{original_filename}' 已成功轉存到 Drive 收件箱 (ID: '{drive_inbox_folder_id}')，新 Drive 檔案 ID 為: {uploaded_drive_file_id}。")

            # 步驟 2: 檔案已在 Drive 收件箱中，現在觸發對這個新 Drive 檔案的標準擷取流程
            # 這會包括下載回本地（到另一個暫存位置）、解析、存入資料庫、然後歸檔到 Drive 的 "已處理" 資料夾
            logger.info(f"開始對剛存入 Drive 的檔案 (ID: {uploaded_drive_file_id}, 名稱: '{original_filename}') 執行標準擷取流程。")
            ingestion_result = await self.ingest_single_drive_file(
                file_id=uploaded_drive_file_id,
                file_name=original_filename,
                original_parent_folder_id=drive_inbox_folder_id, # 此時檔案位於收件箱
                processed_folder_id=drive_processed_folder_id   # 處理後應歸檔到 "已處理" 資料夾
            )

            if ingestion_result:
                logger.info(f"使用者上傳的檔案 '{original_filename}' (原始 Drive ID: {uploaded_drive_file_id}) 已成功完成標準擷取與處理流程。")
                return True
            else:
                logger.error(f"使用者上傳的檔案 '{original_filename}' (原始 Drive ID: {uploaded_drive_file_id}) 在後續的標準擷取流程中處理失敗。")
                # 此時的錯誤狀態應已由 ingest_single_drive_file 內部記錄到資料庫
                return False

        except Exception as e:
            logger.error(f"處理使用者上傳的檔案 '{original_filename}' 過程中發生未預期錯誤: {e}", exc_info=True)
            # 嘗試記錄一個總體的處理異常到資料庫
            await self.dal.insert_report_data(
                    original_filename=original_filename,
                    content=None,
                    source_path=f"upload_processing_exception:{original_filename}",
                    metadata={"error_description": f"Unhandled exception during ingest_uploaded_file: {str(e)}"},
                    status="錯誤(上傳處理異常)" # 中文狀態
                )
            return False
        finally:
            # local_temp_file_path 是 FastAPI 等框架上傳檔案時產生的臨時檔案，
            # 其生命週期通常由框架或調用此函數的端點處理，此處不直接刪除。
            # 如果需要此服務刪除，需明確其職責。
            logger.info(f"本地暫存檔案 '{local_temp_file_path}' 的清理工作應由調用者 (例如 FastAPI 端點) 負責。")
            pass


# 為了能夠進行基本測試 (需要模擬 DriveService 和 DAL 依賴)
if __name__ == '__main__':
    import asyncio

    # --- 用於測試的 Mock (模擬) GoogleDriveService 和 DataAccessLayer ---
    class MockGoogleDriveService:
        async def list_files(self, folder_id: str, page_size: int = 100, fields: str = None) -> list: # 添加 fields 參數以匹配真實簽名
            logger.info(f"[模擬Drive服務] 正在列出資料夾中的檔案: {folder_id}")
            if folder_id == "wolf_in_id_mock": # 模擬的收件箱 ID
                return [
                    {"id": "mock_drive_file_report1.txt", "name": "週報範例1.txt", "mimeType": "text/plain"},
                    {"id": "mock_drive_file_report2.docx", "name": "月度總結.docx", "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
                    {"id": "mock_drive_subfolder", "name": "內部子資料夾", "mimeType": "application/vnd.google-apps.folder"},
                    {"id": "mock_drive_file_report3.pdf", "name": "產品規格書.pdf", "mimeType": "application/pdf"},
                ]
            return []

        async def download_file(self, file_id: str, destination_path: str) -> bool:
            logger.info(f"[模擬Drive服務] 正在下載檔案 '{file_id}' 到 '{destination_path}'")
            os.makedirs(os.path.dirname(destination_path), exist_ok=True) # 確保目標目錄存在
            try:
                mock_content = f"這是檔案 {file_id} 的模擬內容。"
                if "週報範例1.txt" in file_id or "週報範例1.txt" in destination_path : # 讓內容更特定一點
                    mock_content = "這是一份純文字格式的模擬週報內容。"
                elif "月度總結.docx" in file_id or "月度總結.docx" in destination_path:
                    mock_content = "這是一個模擬的 .docx 檔案內容 (非真實 DOCX 格式)。"

                with open(destination_path, 'w', encoding='utf-8') as f:
                    f.write(mock_content)
                logger.info(f"[模擬Drive服務] 檔案 '{file_id}' 已成功模擬下載到 '{destination_path}'。")
                return True
            except Exception as e_mock_dl:
                logger.error(f"[模擬Drive服務] 模擬下載檔案 '{file_id}' 失敗: {e_mock_dl}")
                return False

        async def upload_file(self, local_file_path: str, folder_id: str, file_name: str = None) -> Optional[str]:
            actual_upload_name = file_name if file_name else os.path.basename(local_file_path)
            logger.info(f"[模擬Drive服務] 正在上傳檔案 '{actual_upload_name}' (來源: '{local_file_path}') 到資料夾 '{folder_id}'")
            if not os.path.exists(local_file_path):
                logger.error(f"[模擬Drive服務] 錯誤：本地檔案 {local_file_path} 不存在，無法模擬上傳。")
                return None
            # 模擬生成一個唯一的 Drive 檔案 ID
            mock_uploaded_id = f"mock_uploaded_{actual_upload_name}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            logger.info(f"[模擬Drive服務] 檔案 '{actual_upload_name}' 已成功模擬上傳，模擬 Drive ID: {mock_uploaded_id}")
            return mock_uploaded_id

        async def delete_file(self, file_id: str) -> bool: # 添加 delete_file 的 mock
            logger.info(f"[模擬Drive服務] 正在刪除檔案 ID '{file_id}' (此為模擬操作，實際不刪除)。")
            return True # 假設總是成功


    class MockDataAccessLayer: # 用於測試的模擬資料存取層
        def __init__(self):
            self.reports_data_mock = [] # 模擬資料庫中的報告表
            self.report_id_sequence = 1 # 用於生成唯一的報告 ID

        async def insert_report_data(self, original_filename: str, content: Optional[str], source_path: str, metadata: Optional[dict] = None, status: str = '待處理') -> Optional[int]:
            logger.info(f"[模擬DAL] 正在插入報告: 檔名='{original_filename}', 來源='{source_path}', 狀態='{status}', 元數據='{metadata}'")
            report_entry = {
                "id": self.report_id_sequence,
                "original_filename": original_filename,
                "content": content,
                "source_path": source_path,
                "metadata": metadata if metadata else {},
                "status": status,
                "processed_at": datetime.now().isoformat() # 使用 ISO 格式時間字串
            }
            self.reports_data_mock.append(report_entry)
            self.report_id_sequence += 1
            logger.info(f"[模擬DAL] 報告 '{original_filename}' 已插入，分配 ID: {report_entry['id']}")
            return report_entry["id"]

        async def update_report_status(self, report_id: int, status: str, processed_content: Optional[str] = None) -> bool:
            logger.info(f"[模擬DAL] 正在更新報告 ID {report_id} 的狀態為 '{status}'")
            for report_entry in self.reports_data_mock:
                if report_entry["id"] == report_id:
                    report_entry["status"] = status
                    if processed_content is not None: # 允許傳入 None 來清除內容，或傳入新內容更新
                        report_entry["content"] = processed_content
                    report_entry["processed_at"] = datetime.now().isoformat()
                    logger.info(f"[模擬DAL] 報告 ID {report_id} 狀態更新成功。")
                    return True
            logger.warning(f"[模擬DAL] 更新失敗：未找到報告 ID {report_id}。")
            return False

        def get_report_by_id(self, report_id: int) -> Optional[dict]: # 同步版本用於簡單檢查
            for r_entry in self.reports_data_mock:
                if r_entry['id'] == report_id: return r_entry
            return None

    async def main_test(): # 主測試異步函數
        logger.info("---- 開始 ReportIngestionService 功能測試 (使用模擬依賴) ----")

        # 測試前確保模擬的暫存下載目錄是乾淨的
        if os.path.exists(TEMP_DOWNLOAD_DIR):
             shutil.rmtree(TEMP_DOWNLOAD_DIR) # 清空舊的測試檔案
        os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True) # 重新創建

        mock_drive_service = MockGoogleDriveService()
        mock_dal_service = MockDataAccessLayer()

        report_ingestion_svc = ReportIngestionService(drive_service=mock_drive_service, dal=mock_dal_service)

        logger.info("\n---- 測試從模擬 Drive 資料夾擷取 (ingest_reports_from_drive_folder) ----")
        mock_inbox_id = "wolf_in_id_mock"
        mock_processed_id = "wolf_processed_id_mock"

        num_success, num_failed = await report_ingestion_svc.ingest_reports_from_drive_folder(mock_inbox_id, mock_processed_id)
        logger.info(f"從模擬 Drive 資料夾擷取結果 - 成功處理: {num_success} 個檔案, 處理失敗: {num_failed} 個檔案。")

        logger.info("檢查資料庫 (模擬DAL) 中的報告記錄:")
        for report_item in mock_dal_service.reports_data_mock:
            logger.info(f"  報告 ID: {report_item['id']}, 檔名: {report_item['original_filename']}, 狀態: {report_item['status']}, 內容預覽: '{(report_item.get('content') or '')[:60].replace(os.linesep, ' ')}...'")

        logger.info("\n---- 測試處理使用者上傳的檔案 (ingest_uploaded_file) ----")
        mock_dal_service.reports_data_mock.clear() # 清空先前的記錄以便觀察

        # 創建一個模擬的本地上傳檔案
        user_uploaded_filename = "使用者上傳的報告.txt"
        user_uploaded_temp_path = os.path.join(TEMP_DOWNLOAD_DIR, user_uploaded_filename)
        with open(user_uploaded_temp_path, 'w', encoding='utf-8') as f_upload:
            f_upload.write("這是一份由使用者直接上傳的純文字報告檔案，用於測試擷取流程。")

        upload_ingest_success = await report_ingestion_svc.ingest_uploaded_file(
            local_temp_file_path=user_uploaded_temp_path,
            original_filename=user_uploaded_filename,
            drive_inbox_folder_id=mock_inbox_id, # 假設上傳後也先到收件箱
            drive_processed_folder_id=mock_processed_id
        )
        logger.info(f"處理使用者上傳檔案 '{user_uploaded_filename}' 的結果 - 是否成功: {upload_ingest_success}")

        logger.info("檢查資料庫 (模擬DAL) 中關於上傳檔案的記錄:")
        for report_item in mock_dal_service.reports_data_mock:
            logger.info(f"  報告 ID: {report_item['id']}, 檔名: {report_item['original_filename']}, 狀態: {report_item['status']}, 來源路徑: {report_item['source_path']}")

        # 清理測試產生的暫存目錄
        if os.path.exists(TEMP_DOWNLOAD_DIR):
             shutil.rmtree(TEMP_DOWNLOAD_DIR)
             logger.info(f"已清理並移除臨時下載目錄: {TEMP_DOWNLOAD_DIR}")

    # 設定 Windows 環境的 asyncio 事件迴圈策略 (如果適用)
    if os.name == 'nt': # 'nt' 通常指 Windows
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main_test()) # 執行主測試函數
