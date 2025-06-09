import os
import logging
import shutil
from datetime import datetime
from typing import TYPE_CHECKING, Tuple, Optional, List

if TYPE_CHECKING:
    from .google_drive_service import GoogleDriveService
    from .data_access_layer import DataAccessLayer

logger = logging.getLogger(__name__)

SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SERVICE_DIR)
TEMP_DOWNLOAD_DIR = os.path.join(BACKEND_DIR, 'data', 'temp_downloads')

os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)
logger.info(f"報告擷取服務：暫存下載目錄設定於 '{TEMP_DOWNLOAD_DIR}'。")

class ReportIngestionService:
    def __init__(self, drive_service: 'GoogleDriveService', dal: 'DataAccessLayer'):
        self.drive_service = drive_service
        self.dal = dal
        logger.info("報告擷取服務 (ReportIngestionService) 已初始化。")

    def _get_file_extension(self, file_name: str) -> str:
        return os.path.splitext(file_name)[1].lower()

    async def _parse_report_content(self, local_file_path: str) -> str:
        file_extension = self._get_file_extension(local_file_path)
        content = ""
        logger.info(f"開始解析檔案 '{local_file_path}' (類型: {file_extension})...")
        try:
            if file_extension in [".txt", ".md"]:
                with open(local_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                logger.info(f"成功解析純文字檔案: {local_file_path}")
            elif file_extension == ".docx":
                logger.warning(f"注意：.docx ({local_file_path}) 內容解析功能待實現。")
                content = "[.docx 檔案內容解析功能待實現]"
            elif file_extension == ".pdf":
                logger.warning(f"注意：.pdf ({local_file_path}) 內容解析功能待實現。")
                content = "[.pdf 檔案內容解析功能待實現]"
            else:
                logger.warning(f"不支援的檔案類型 '{file_extension}' ({local_file_path})。")
                content = f"[不支援的檔案類型: {file_extension}]"
        except Exception as e:
            logger.error(f"解析檔案 '{local_file_path}' 發生錯誤: {e}", exc_info=True)
            content = f"[檔案內容解析錯誤: {str(e)}]"
        return content

    async def _archive_file_in_drive(self, file_id: str, file_name: str, processed_folder_id: str, original_parent_folder_id: str) -> Optional[str]:
        logger.info(f"準備從來源資料夾 '{original_parent_folder_id}' 刪除原始檔案 '{file_name}' (ID: {file_id})。")
        try:
            if hasattr(self.drive_service, 'delete_file'):
                delete_success = await self.drive_service.delete_file(file_id)
                if delete_success:
                    logger.info(f"成功刪除已處理的檔案 '{file_name}'。")
                    return "deleted_from_inbox"
                else:
                    logger.warning(f"刪除檔案 '{file_name}' 操作未成功。")
                    return "delete_from_inbox_failed"
            else:
                logger.warning("`GoogleDriveService` 未找到 `delete_file` 方法。")
                return "delete_skipped_no_method"
        except Exception as e:
            logger.error(f"歸檔 (刪除) 檔案 '{file_name}' 時發生錯誤: {e}", exc_info=True)
            return "delete_exception"

    async def ingest_single_drive_file(self, file_id: str, file_name: str, original_parent_folder_id: str, processed_folder_id: str) -> bool:
        local_download_path = os.path.join(TEMP_DOWNLOAD_DIR, f"drive_{file_id}_{file_name}")
        report_db_id = None
        content = ""
        try:
            logger.info(f"開始處理 Drive 檔案: '{file_name}' (ID: {file_id})。")
            if not await self.drive_service.download_file(file_id, local_download_path):
                logger.error(f"下載 Drive 檔案 '{file_name}' 失敗。")
                await self.dal.insert_report_data(
                    original_filename=file_name,
                    content=None,
                    source_path=f"drive_id:{file_id}",
                    metadata={"error": "download_failed"},
                    status="擷取錯誤(下載失敗)"
                )
                return False

            content = await self._parse_report_content(local_download_path)
            report_db_id = await self.dal.insert_report_data(
                original_filename=file_name,
                content=content,
                source_path=f"drive_id:{file_id}",
                metadata={"drive_file_id": file_id},
                status="已擷取待處理"
            )

            if not report_db_id:
                logger.error(f"將報告 '{file_name}' 存入資料庫失敗。")
            else:
                await self.dal.update_report_status(report_db_id, "內容已解析", processed_content=content)

            archived_file_id = await self.drive_service.upload_file(
                local_file_path=local_download_path,
                folder_id=processed_folder_id,
                file_name=file_name
            )

            if archived_file_id:
                await self._archive_file_in_drive(file_id, file_name, processed_folder_id, original_parent_folder_id)
                if report_db_id:
                    await self.dal.update_report_status(report_db_id, "已歸檔至Drive", processed_content=content)
                return True
            else:
                logger.error(f"歸檔檔案 '{file_name}' 失敗。")
                if report_db_id:
                    await self.dal.update_report_status(report_db_id, "擷取錯誤(歸檔失敗)", processed_content=content)
                return False
        except Exception as e:
            logger.error(f"處理 Drive 檔案 '{file_name}' 時發生未預期錯誤: {e}", exc_info=True)
            if report_db_id:
                await self.dal.update_report_status(report_db_id, "擷取錯誤(處理異常)", processed_content=content)
            return False
        finally:
            if os.path.exists(local_download_path):
                os.remove(local_download_path)

    # ... (檔案的其餘部分，如 ingest_reports_from_drive_folder, ingest_uploaded_file 等，保持不變) ...
