import os
import logging
import shutil # 用於檔案操作，例如刪除暫存檔案
from datetime import datetime
from typing import TYPE_CHECKING, Tuple, Optional, List

if TYPE_CHECKING:
    from .google_drive_service import GoogleDriveService
    from .data_access_layer import DataAccessLayer

# 配置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 暫存下載檔案的目錄
# Correcting the path to be relative to this file's location then up to backend/data/temp_downloads
SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SERVICE_DIR)
TEMP_DOWNLOAD_DIR = os.path.join(BACKEND_DIR, 'data', 'temp_downloads')

# 確保暫存目錄存在
os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)

class ReportIngestionService:
    def __init__(self, drive_service: 'GoogleDriveService', dal: 'DataAccessLayer'):
        self.drive_service = drive_service
        self.dal = dal
        logger.info("ReportIngestionService initialized.")

    def _get_file_extension(self, file_name: str) -> str:
        return os.path.splitext(file_name)[1].lower()

    async def _parse_report_content(self, local_file_path: str) -> str:
        """
        解析本地報告檔案的內容。
        初期支援 .txt。其他格式記錄訊息。
        """
        file_extension = self._get_file_extension(local_file_path)
        content = ""
        try:
            if file_extension == ".txt":
                with open(local_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                logger.info(f"成功解析純文字檔案: {local_file_path}")
            elif file_extension == ".md": # Markdown 也是純文字
                with open(local_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                logger.info(f"成功解析 Markdown 檔案: {local_file_path}")
            # TODO: 添加對 .docx, .pdf 等格式的解析邏輯
            # 例如使用 python-docx, pypdf2
            elif file_extension == ".docx":
                logger.warning(f"docx 檔案 ({local_file_path}) 的內容解析功能尚未實現。")
                content = "[DOCX內容解析未實現]"
            elif file_extension == ".pdf":
                logger.warning(f"pdf 檔案 ({local_file_path}) 的內容解析功能尚未實現。")
                content = "[PDF內容解析未實現]"
            else:
                logger.warning(f"不支援的檔案類型 '{file_extension}' 用於內容解析: {local_file_path}")
                content = f"[不支援的檔案類型: {file_extension}]"
        except Exception as e:
            logger.error(f"解析檔案 '{local_file_path}' 時發生錯誤: {e}")
            content = f"[檔案解析錯誤: {e}]"
        return content

    async def _archive_file_in_drive(self, file_id: str, file_name: str, processed_folder_id: str, original_parent_folder_id: str) -> Optional[str]:
        """
        將 Drive 中的檔案移動到 'processed' 資料夾。
        Google Drive API 移動檔案是透過更新其 parents 屬性來實現的。
        首先複製，然後從原位置刪除是更安全的方式，但 Drive API 也支援直接更新 parent。
        這裡我們採用先複製到 processed，再從 inbox 刪除的策略。
        或者，如果 GoogleDriveService 有 move_file 方法，則直接使用。

        簡化：先上傳一個副本到 processed folder，然後可以選擇是否刪除原檔案。
        計畫書提到的是「歸檔」，通常是移動。
        目前 GoogleDriveService 沒有 move_file 或 delete_file。
        我們將檔案複製 (upload) 到 processed 資料夾。刪除操作待定。
        """
        # 這裡假設 self.drive_service.upload_file 可以處理從一個 Drive ID 複製到另一個位置，
        # 或者它需要先下載再上傳。
        # 根據目前的 GoogleDriveService.upload_file(local_file_path, folder_id, file_name)
        # 我們需要先下載檔案，然後再上傳到 processed folder。
        # 這在 ingest_single_drive_file 已經做了下載，所以這裡只需要上傳。
        # 但我們已經在 ingest_single_drive_file 中將下載的檔案上傳到 processed folder。
        # 所以此函數的職責更像是確保原始檔案被處理 (例如刪除)。
        # 為簡化，此函數暫時只記錄操作，實際的歸檔（移動/刪除）邏輯需要在 GoogleDriveService 中增強。

        logger.info(f"檔案 '{file_name}' (ID: {file_id}) 已處理。歸檔操作 (移動到 {processed_folder_id}) 待 GoogleDriveService 增強。")
        # 假設 drive_service 有 delete_file 方法
        # success = await self.drive_service.delete_file(file_id)
        # if success:
        #     logger.info(f"已從來源資料夾 '{original_parent_folder_id}' 刪除已處理的檔案 '{file_name}' (ID: {file_id})。")
        #     return "deleted"
        # else:
        #     logger.warning(f"從來源資料夾 '{original_parent_folder_id}' 刪除檔案 '{file_name}' (ID: {file_id}) 失敗。")
        #     return "delete_failed"
        return "archive_pending_delete_implementation"


    async def ingest_single_drive_file(self, file_id: str, file_name: str, original_parent_folder_id: str, processed_folder_id: str) -> bool:
        """
        處理單個在 Drive 中的檔案：下載、解析、存入資料庫、移動到已處理資料夾。
        """
        # Ensure TEMP_DOWNLOAD_DIR is created before trying to use it
        os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)
        local_download_path = os.path.join(TEMP_DOWNLOAD_DIR, f"{file_id}_{file_name}")
        processed_successfully = False
        report_db_id = None # Initialize report_db_id
        try:
            logger.info(f"開始處理 Drive 檔案: '{file_name}' (ID: {file_id}) 從資料夾 '{original_parent_folder_id}'。")

            # 1. 下載檔案
            download_success = await self.drive_service.download_file(file_id, local_download_path)
            if not download_success:
                logger.error(f"下載 Drive 檔案 '{file_name}' (ID: {file_id}) 失敗。")
                report_db_id = await self.dal.insert_report_data(
                    original_filename=file_name,
                    content=None,
                    source_path=f"drive_id:{file_id}",
                    metadata={"error": "download failed", "drive_folder_id": original_parent_folder_id},
                    status="error_download"
                )
                return False

            # 2. 解析內容
            logger.info(f"檔案 '{file_name}' 已下載到 '{local_download_path}'，準備解析。")
            content = await self._parse_report_content(local_download_path)

            # 3. 寫入資料庫 (無論解析是否完美，都記錄下來)
            # source_path 可以存儲 Drive File ID
            report_db_id = await self.dal.insert_report_data(
                original_filename=file_name,
                content=content,
                source_path=f"drive_id:{file_id}", # 標記來源為 Drive
                metadata={"drive_file_id": file_id, "drive_folder_id": original_parent_folder_id}
            )

            if not report_db_id:
                logger.error(f"將報告 '{file_name}' (ID: {file_id}) 存入資料庫失敗。")
                # 即使存儲失敗，也嘗試歸檔，避免重複處理問題檔案
            else:
                logger.info(f"報告 '{file_name}' (ID: {file_id}) 已存入資料庫，記錄 ID: {report_db_id}.")
                # 更新狀態為 processed (如果解析和存儲都視為初步處理完成)
                await self.dal.update_report_status(report_db_id, "processed_from_drive", processed_content=content)


            # 4. 將原始檔案歸檔 (移動到 processed 資料夾)
            # 實現方式：將本地下載的檔案重新上傳到 processed_folder_id
            # 注意：這會創建一個新檔案，而不是移動原始檔案。真正的移動需要 Drive API 的 files.update(parents=[...])
            # 或者 files.copy 然後 files.delete。
            # 為了符合計畫書的 "歸檔"，我們將使用 "上傳副本到 processed" + "從 inbox 刪除 (待實現)"

            # 上傳到 processed 資料夾
            archived_file_id = await self.drive_service.upload_file(
                local_file_path=local_download_path,
                folder_id=processed_folder_id,
                file_name=file_name # 保留原始檔案名
            )

            if archived_file_id:
                logger.info(f"檔案 '{file_name}' 的副本已歸檔到 Drive 資料夾 ID '{processed_folder_id}'，新檔案 ID: {archived_file_id}.")
                # 歸檔成功後，可以從原始位置刪除 (需要 drive_service.delete_file(file_id))
                # delete_status = await self._archive_file_in_drive(file_id, file_name, processed_folder_id, original_parent_folder_id)
                # logger.info(f"原始檔案 '{file_name}' (ID: {file_id}) 處理狀態: {delete_status}")
                # 目前 GoogleDriveService 沒有 delete_file，所以先跳過刪除
                logger.warning(f"原始檔案 '{file_name}' (ID: {file_id}) 的刪除操作待 GoogleDriveService.delete_file() 實現後處理。")
                if report_db_id: # Update status to fully processed if DB entry exists
                    await self.dal.update_report_status(report_db_id, "archived_to_drive", processed_content=content)
                processed_successfully = True
            else:
                logger.error(f"歸檔檔案 '{file_name}' (ID: {file_id}) 到 Drive 資料夾 ID '{processed_folder_id}' 失敗。")
                if report_db_id: # 如果之前存儲成功，更新狀態為錯誤
                    await self.dal.update_report_status(report_db_id, "error_archiving", processed_content=content)
                processed_successfully = False

        except Exception as e:
            logger.error(f"處理 Drive 檔案 '{file_name}' (ID: {file_id}) 時發生未預期錯誤: {e}", exc_info=True)
            if report_db_id: # If DB entry was created before exception
                 await self.dal.update_report_status(report_db_id, "error_processing", processed_content=content if 'content' in locals() else None)
            elif file_id: # If DB entry was not created
                 await self.dal.insert_report_data(
                    original_filename=file_name,
                    content=None,
                    source_path=f"drive_id:{file_id}",
                    metadata={"error": f"processing exception: {str(e)}", "drive_folder_id": original_parent_folder_id},
                    status="error_exception"
                )
            processed_successfully = False
        finally:
            # 5. 清理本地暫存檔案
            if os.path.exists(local_download_path):
                try:
                    os.remove(local_download_path)
                    logger.info(f"已刪除暫存檔案: {local_download_path}")
                except Exception as e:
                    logger.error(f"刪除暫存檔案 '{local_download_path}' 失敗: {e}")
        return processed_successfully

    async def ingest_reports_from_drive_folder(self, inbox_folder_id: str, processed_folder_id: str) -> Tuple[int, int]:
        """
        從指定的 Drive 資料夾 (wolf_in) 擷取所有報告檔案。
        :param inbox_folder_id: Drive 中待處理報告的入口資料夾 ID。
        :param processed_folder_id: Drive 中已成功處理報告的歸檔位置 ID。
        :return: (成功處理的檔案數量, 失敗的檔案數量)
        """
        logger.info(f"開始從 Drive 資料夾 ID '{inbox_folder_id}' 擷取報告...")
        successful_ingestions = 0
        failed_ingestions = 0
        files_in_inbox = [] # Initialize to ensure it's available in except block

        try:
            # 1. 列出 'wolf_in' 中的檔案
            files_in_inbox = await self.drive_service.list_files(folder_id=inbox_folder_id)
            if not files_in_inbox:
                logger.info(f"Drive 資料夾 '{inbox_folder_id}' 中沒有找到任何檔案。")
                return 0, 0

            logger.info(f"在 '{inbox_folder_id}' 中找到 {len(files_in_inbox)} 個項目。開始處理...")

            for drive_file in files_in_inbox:
                file_id = drive_file.get('id')
                file_name = drive_file.get('name')
                mime_type = drive_file.get('mimeType')

                if not file_id or not file_name:
                    logger.warning(f"跳過一個無效的 Drive 項目: {drive_file}")
                    failed_ingestions +=1
                    continue

                # 避免處理 Google Drive 的資料夾本身
                if mime_type == 'application/vnd.google-apps.folder':
                    logger.info(f"跳過子資料夾 '{file_name}' (ID: {file_id})。擷取服務目前不遞歸處理子資料夾。")
                    continue

                logger.info(f"準備處理檔案: {file_name} (ID: {file_id}, Type: {mime_type})")

                if await self.ingest_single_drive_file(file_id, file_name, inbox_folder_id, processed_folder_id):
                    successful_ingestions += 1
                else:
                    failed_ingestions += 1

        except Exception as e:
            logger.error(f"從 Drive 資料夾 '{inbox_folder_id}' 擷取報告時發生嚴重錯誤: {e}", exc_info=True)
            # Count remaining files as failed if a general error occurred
            remaining_files = len(files_in_inbox) - successful_ingestions - failed_ingestions
            failed_ingestions += remaining_files
            return successful_ingestions, failed_ingestions

        logger.info(f"從 Drive 資料夾 '{inbox_folder_id}' 擷取完成。成功: {successful_ingestions}，失敗: {failed_ingestions}。")
        return successful_ingestions, failed_ingestions

    async def ingest_uploaded_file(
        self,
        local_temp_file_path: str, # 後端接收到的上傳檔案的暫存路徑
        original_filename: str,    # 使用者上傳時的原始檔案名
        drive_inbox_folder_id: str, # Drive 中的 "wolf_in" 資料夾 ID
        drive_processed_folder_id: str # Drive 中的 "wolf_in/processed" 資料夾 ID
    ) -> bool:
        """
        處理前端上傳的單個檔案。
        流程：
        1. 將本地暫存檔案上傳到 Drive 的 'wolf_in' 資料夾。
        2. 觸發對該 Drive 檔案的標準擷取流程 (下載、解析、存庫、歸檔)。
        """
        logger.info(f"開始處理上傳的檔案: '{original_filename}' (本地路徑: '{local_temp_file_path}')")

        try:
            # 1. 將本地暫存檔案上傳到 Drive 的 'wolf_in' 資料夾
            uploaded_drive_file_id = await self.drive_service.upload_file(
                local_file_path=local_temp_file_path,
                folder_id=drive_inbox_folder_id,
                file_name=original_filename
            )

            if not uploaded_drive_file_id:
                logger.error(f"將上傳的檔案 '{original_filename}' 上傳到 Drive 資料夾 '{drive_inbox_folder_id}' 失敗。")
                await self.dal.insert_report_data(
                    original_filename=original_filename,
                    content=None,
                    source_path=f"upload_failed_to_drive:{original_filename}",
                    metadata={"error": "upload to drive inbox failed"},
                    status="error_upload_to_drive"
                )
                return False

            logger.info(f"上傳的檔案 '{original_filename}' 已成功存入 Drive 資料夾 '{drive_inbox_folder_id}'，新檔案 ID: {uploaded_drive_file_id}.")

            # 2. 現在該檔案已經在 'wolf_in' 中了，觸發對這個新 Drive 檔案的擷取流程
            ingestion_result = await self.ingest_single_drive_file(
                file_id=uploaded_drive_file_id,
                file_name=original_filename,
                original_parent_folder_id=drive_inbox_folder_id,
                processed_folder_id=drive_processed_folder_id
            )

            if ingestion_result:
                logger.info(f"上傳的檔案 '{original_filename}' 已成功擷取並處理。")
                return True
            else:
                logger.error(f"上傳的檔案 '{original_filename}' (Drive ID: {uploaded_drive_file_id}) 在後續擷取流程中處理失敗。")
                return False

        except Exception as e:
            logger.error(f"處理上傳檔案 '{original_filename}' 時發生未預期錯誤: {e}", exc_info=True)
            await self.dal.insert_report_data(
                    original_filename=original_filename,
                    content=None,
                    source_path=f"upload_exception:{original_filename}",
                    metadata={"error": f"ingest_uploaded_file exception: {str(e)}"},
                    status="error_exception_upload"
                )
            return False
        finally:
            # The local_temp_file_path is managed by the caller (e.g., FastAPI endpoint)
            # It should be cleaned up there after this method returns.
            pass


# 為了能夠進行基本測試 (需要模擬 DriveService 和 DAL)
if __name__ == '__main__':
    import asyncio

    # --- Mockups for GoogleDriveService and DataAccessLayer ---
    class MockGoogleDriveService:
        async def list_files(self, folder_id: str, page_size: int = 100) -> list:
            logger.info(f"[MockDriveService] Listing files in folder: {folder_id}")
            if folder_id == "wolf_in_id":
                return [
                    {"id": "drive_file_1_txt", "name": "report1.txt", "mimeType": "text/plain"},
                    {"id": "drive_file_2_docx", "name": "report2.docx", "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
                    {"id": "drive_folder_sub", "name": "subfolder", "mimeType": "application/vnd.google-apps.folder"},
                    {"id": "drive_file_3_pdf", "name": "report3.pdf", "mimeType": "application/pdf"},
                ]
            return []

        async def download_file(self, file_id: str, destination_path: str) -> bool:
            logger.info(f"[MockDriveService] Downloading file '{file_id}' to '{destination_path}'")
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)
            try:
                file_content = f"Mock content for file {file_id}"
                if "txt" in file_id:
                    file_content = "This is a sample text report."
                elif "docx" in file_id:
                    file_content = "This is a mock docx (not real content)."
                with open(destination_path, 'w', encoding='utf-8') as f:
                    f.write(file_content)
                return True
            except Exception as e:
                logger.error(f"[MockDriveService] Mock download failed: {e}")
                return False

        async def upload_file(self, local_file_path: str, folder_id: str, file_name: str = None) -> Optional[str]:
            actual_file_name = file_name if file_name else os.path.basename(local_file_path)
            logger.info(f"[MockDriveService] Uploading file '{actual_file_name}' from '{local_file_path}' to folder '{folder_id}'")
            if not os.path.exists(local_file_path):
                logger.error(f"[MockDriveService] Local file {local_file_path} does not exist for upload.")
                return None
            return f"uploaded_{actual_file_name}_{datetime.now().strftime('%H%M%S')}"

        async def delete_file(self, file_id: str) -> bool:
            logger.info(f"[MockDriveService] Deleting file '{file_id}' (Not implemented in this mock)")
            return True


    class MockDataAccessLayer:
        def __init__(self):
            self.reports = []
            self.report_id_counter = 1

        async def insert_report_data(self, original_filename: str, content: Optional[str], source_path: str, metadata: Optional[dict] = None, status: str = 'pending') -> Optional[int]:
            logger.info(f"[MockDAL] Inserting report: {original_filename}, source: {source_path}, status: {status}, metadata: {metadata}")
            report = {
                "id": self.report_id_counter,
                "original_filename": original_filename,
                "content": content,
                "source_path": source_path,
                "metadata": metadata,
                "status": status,
                "processed_at": datetime.now()
            }
            self.reports.append(report)
            self.report_id_counter += 1
            return report["id"]

        async def update_report_status(self, report_id: int, status: str, processed_content: Optional[str] = None) -> bool:
            logger.info(f"[MockDAL] Updating report ID {report_id} to status {status}")
            for report in self.reports:
                if report["id"] == report_id:
                    report["status"] = status
                    if processed_content is not None: # Allow clearing content if explicitly None
                        report["content"] = processed_content
                    report["processed_at"] = datetime.now()
                    return True
            logger.warning(f"[MockDAL] Report ID {report_id} not found for update.")
            return False

        def get_report_by_id(self, report_id: int):
            for r in self.reports:
                if r['id'] == report_id: return r
            return None

    async def main_test():
        logger.info("---- 測試 ReportIngestionService (使用 Mock 依賴) ----")

        # Ensure TEMP_DOWNLOAD_DIR is clean and exists before tests
        if os.path.exists(TEMP_DOWNLOAD_DIR):
             shutil.rmtree(TEMP_DOWNLOAD_DIR)
        os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)

        mock_drive = MockGoogleDriveService()
        mock_dal = MockDataAccessLayer()

        ingestion_service = ReportIngestionService(drive_service=mock_drive, dal=mock_dal)

        logger.info("\n---- 測試從 Drive 資料夾擷取 (ingest_reports_from_drive_folder) ----")
        inbox_id = "wolf_in_id"
        processed_id = "wolf_processed_id"

        success_count, fail_count = await ingestion_service.ingest_reports_from_drive_folder(inbox_id, processed_id)
        logger.info(f"從 Drive 資料夾擷取結果 - 成功: {success_count}, 失敗: {fail_count}")

        logger.info("資料庫中的報告 (MockDAL):")
        for rep in mock_dal.reports:
            logger.info(f"  ID: {rep['id']}, Name: {rep['original_filename']}, Status: {rep['status']}, Content Preview: {(rep.get('content') or '')[:50]}...")

        logger.info("\n---- 測試處理上傳的檔案 (ingest_uploaded_file) ----")
        mock_dal.reports.clear()
        temp_upload_file_name = "uploaded_report.txt"
        temp_upload_file_path = os.path.join(TEMP_DOWNLOAD_DIR, temp_upload_file_name)
        with open(temp_upload_file_path, 'w', encoding='utf-8') as f:
            f.write("This is a report uploaded directly by the user.")

        upload_success = await ingestion_service.ingest_uploaded_file(
            local_temp_file_path=temp_upload_file_path,
            original_filename=temp_upload_file_name,
            drive_inbox_folder_id=inbox_id,
            drive_processed_folder_id=processed_id
        )
        logger.info(f"處理上傳檔案結果 - 成功: {upload_success}")
        logger.info("資料庫中的報告 (MockDAL) after upload test:")
        for rep in mock_dal.reports:
            logger.info(f"  ID: {rep['id']}, Name: {rep['original_filename']}, Status: {rep['status']}, Source: {rep['source_path']}")

        if os.path.exists(TEMP_DOWNLOAD_DIR):
             shutil.rmtree(TEMP_DOWNLOAD_DIR)


    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main_test())
