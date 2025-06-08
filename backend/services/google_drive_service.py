import os
import logging
import json
import time # For test_main unique naming
from aiogoogle import Aiogoogle
from aiogoogle.auth.creds import ServiceAccountCreds
# from googleapiclient.errors import HttpError # aiogoogle raises its own errors, typically aiogoogle.excs.HTTPError or similar

# 配置日誌記錄器 (可能已被 FastAPI 的 main.py 預先配置，但為服務保留一個特定的日誌記錄器是好習慣)
logger = logging.getLogger(__name__)
# 如果作為獨立腳本運行以進行測試，請確保 basicConfig 已設定。
if not logger.hasHandlers(): # 檢查是否已有處理器，避免重複設定
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


# Google Drive API 的授權範圍
DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive']

class GoogleDriveService:
    def __init__(self, service_account_info: dict = None, service_account_json_path: str = None):
        """
        初始化 Google Drive 服務。
        優先使用 service_account_info (字典形式的憑證)，其次是 service_account_json_path (檔案路徑)。
        :param service_account_info: 直接傳入的服務帳號憑證字典。
        :param service_account_json_path: 服務帳號 JSON 金鑰檔案的路徑。
        :raises ValueError: 如果憑證資訊無效或未提供。
        :raises FileNotFoundError: 如果 service_account_json_path 指向的檔案不存在。
        """
        self.service_account_creds = None

        if service_account_info:
            try:
                self.service_account_creds = ServiceAccountCreds(
                    scopes=DRIVE_SCOPES,
                    **service_account_info  # 解包字典以傳遞 client_email, private_key 等參數
                )
                logger.info("Google Drive 服務：已使用傳入的 service_account_info 初始化憑證。")
            except Exception as e:
                logger.error(f"Google Drive 服務：從 service_account_info 初始化憑證失敗: {e}", exc_info=True)
                raise ValueError(f"無效的 service_account_info: {e}")
        elif service_account_json_path:
            try:
                if not os.path.exists(service_account_json_path):
                    logger.error(f"Google Drive 服務：服務帳號 JSON 檔案路徑不存在: {service_account_json_path}")
                    raise FileNotFoundError(f"服務帳號 JSON 檔案未找到: {service_account_json_path}")

                with open(service_account_json_path, 'r', encoding='utf-8') as f: # 指定 UTF-8 編碼
                    sa_info_from_file = json.load(f)

                self.service_account_creds = ServiceAccountCreds(
                    scopes=DRIVE_SCOPES,
                    **sa_info_from_file
                )
                logger.info(f"Google Drive 服務：已從 JSON 檔案 {service_account_json_path} 初始化憑證。")
            except Exception as e:
                logger.error(f"Google Drive 服務：從 JSON 檔案 {service_account_json_path} 初始化憑證失敗: {e}", exc_info=True)
                raise ValueError(f"從 JSON 檔案 {service_account_json_path} 初始化憑證失敗: {e}")
        else:
            logger.error("Google Drive 服務：必須提供 service_account_info 或 service_account_json_path。")
            raise ValueError("未提供有效的 Google Drive 服務帳號憑證。")

        self.aiogoogle = Aiogoogle(service_account_creds=self.service_account_creds)
        logger.info("GoogleDriveService 初始化完成，Aiogoogle 客戶端已配置。")

    async def list_files(self, folder_id: str = 'root', page_size: int = 100, fields: str = "nextPageToken, files(id, name, mimeType, modifiedTime, parents)") -> list:
        """
        列出指定 Google Drive 資料夾中的檔案和子資料夾。
        :param folder_id: 要列出內容的資料夾 ID，預設為 'root' (根目錄)。
        :param page_size: 每頁返回的項目數量。
        :param fields: 指定 API 回應中包含哪些檔案欄位。
        :return: 檔案/資料夾物件的列表。
        """
        logger.info(f"正在列出 Drive 資料夾 '{folder_id}' 中的檔案...")
        all_files = []
        page_token = None
        try:
            async with self.aiogoogle as google:
                drive_v3 = await google.discover('drive', 'v3')
                while True:
                    query = f"'{folder_id}' in parents and trashed=false" # 查詢條件：父資料夾為 folder_id 且未被刪除
                    response = await google.as_service_account(
                        drive_v3.files.list(
                            q=query,
                            pageSize=min(page_size, 1000), # API 上限為 1000
                            fields=fields,
                            pageToken=page_token,
                            corpora="user" # 指定查詢使用者個人的 Drive
                        )
                    )
                    files = response.get('files', [])
                    all_files.extend(files)
                    page_token = response.get('nextPageToken') # 獲取下一頁的 token
                    if not page_token: # 如果沒有下一頁，則結束迴圈
                        break
            logger.info(f"成功列出資料夾 '{folder_id}' 中的 {len(all_files)} 個項目。")
            return all_files
        except Exception as e:
            logger.error(f"列出 Drive 資料夾 '{folder_id}' 中的檔案時發生錯誤: {e}", exc_info=True)
            return []

    async def download_file(self, file_id: str, destination_path: str) -> bool:
        """
        從 Google Drive 下載檔案。
        :param file_id: 要下載的檔案 ID。
        :param destination_path: 檔案下載到本地的完整路徑。
        :return: 如果下載成功返回 True，否則返回 False。
        """
        logger.info(f"準備從 Drive 下載檔案 ID '{file_id}' 到 '{destination_path}'...")
        try:
            async with self.aiogoogle as google:
                drive_v3 = await google.discover('drive', 'v3')

                # 首先獲取檔案元數據，檢查是否為資料夾
                file_metadata_req = drive_v3.files.get(fileId=file_id, fields="mimeType, name")
                file_metadata = await google.as_service_account(file_metadata_req)

                if file_metadata.get('mimeType') == 'application/vnd.google-apps.folder':
                    logger.error(f"錯誤：項目 ID '{file_id}' (名稱: '{file_metadata.get('name')}') 是一個資料夾，無法直接下載。")
                    return False

                # 確保目標目錄存在
                os.makedirs(os.path.dirname(destination_path), exist_ok=True)

                # 準備下載請求
                download_req = drive_v3.files.get(
                    fileId=file_id,
                    alt="media", # 指示下載檔案內容
                    download_file=destination_path # aiogoogle 會處理檔案寫入
                )
                # 使用 as_service_account 執行請求
                response = await google.as_service_account(download_req, full_res=True) # full_res=True 獲取完整回應

                if response.status_code == 200:
                    logger.info(f"檔案 ID '{file_id}' 已成功下載到 '{destination_path}'。")
                    return True
                else:
                    error_content = await response.text() # 獲取錯誤回應的文本內容
                    logger.error(f"下載檔案 ID '{file_id}' 失敗。狀態碼: {response.status_code}, 回應: {error_content}")
                    return False
        except Exception as e:
            logger.error(f"下載檔案 ID '{file_id}' 時發生未預期錯誤: {e}", exc_info=True)
            return False

    async def upload_file(self, local_file_path: str, folder_id: str = None, file_name: str = None) -> str | None:
        """
        將本地檔案上傳到 Google Drive。
        :param local_file_path: 要上傳的本地檔案的完整路徑。
        :param folder_id: 目標 Drive 資料夾的 ID。如果為 None，則上傳到根目錄。
        :param file_name: 在 Drive 中儲存的檔案名。如果為 None，則使用本地檔案名。
        :return: 上傳成功則返回新檔案的 Drive File ID，否則返回 None。
        """
        if not os.path.exists(local_file_path):
            logger.error(f"本地檔案 '{local_file_path}' 未找到，無法上傳。")
            return None

        drive_file_name = file_name if file_name else os.path.basename(local_file_path)
        logger.info(f"準備將本地檔案 '{local_file_path}' 作為 '{drive_file_name}' 上傳到 Drive 資料夾 ID '{folder_id}'...")

        file_metadata = {'name': drive_file_name}
        if folder_id:
            file_metadata['parents'] = [folder_id]

        try:
            async with self.aiogoogle as google:
                drive_v3 = await google.discover('drive', 'v3')
                response = await google.as_service_account(
                    drive_v3.files.create(
                        upload_file=local_file_path, # 指定本地檔案路徑進行上傳
                        json=file_metadata,          # 檔案元數據
                        fields='id, name'            # 要求回應中包含新檔案的 ID 和名稱
                    )
                )
            uploaded_file_id = response.get('id')
            if uploaded_file_id:
                logger.info(f"檔案 '{drive_file_name}' 已成功上傳到 Drive。新檔案 ID: {uploaded_file_id}")
                return uploaded_file_id
            else:
                logger.error(f"上傳檔案 '{drive_file_name}' 失敗。Drive API 未返回檔案 ID。回應: {response}")
                return None
        except Exception as e:
            logger.error(f"上傳檔案 '{drive_file_name}' 時發生錯誤: {e}", exc_info=True)
            return None

    async def create_folder(self, folder_name: str, parent_folder_id: str = None) -> str | None:
        """
        在指定的父資料夾下創建一個新資料夾。如果 parent_folder_id 為 None，則在根目錄創建。
        :param folder_name: 要創建的新資料夾的名稱。
        :param parent_folder_id: 父資料夾的 ID。
        :return: 創建成功則返回新資料夾的 Drive Folder ID，否則返回 None。
        """
        logger.info(f"準備在父資料夾 ID '{parent_folder_id if parent_folder_id else 'root'}' 下創建資料夾 '{folder_name}'...")
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder' # 指定 MIME 類型為資料夾
        }
        if parent_folder_id:
            file_metadata['parents'] = [parent_folder_id]

        try:
            async with self.aiogoogle as google:
                drive_v3 = await google.discover('drive', 'v3')
                folder = await google.as_service_account(
                    drive_v3.files.create(json=file_metadata, fields='id, name')
                )
            folder_id = folder.get('id')
            if folder_id:
                logger.info(f"資料夾 '{folder_name}' (ID: {folder_id}) 已成功創建。")
                return folder_id
            else:
                logger.error(f"創建資料夾 '{folder_name}' 失敗。Drive API 未返回 ID。回應: {folder}")
                return None
        except Exception as e:
            logger.error(f"創建資料夾 '{folder_name}' 時發生錯誤: {e}", exc_info=True)
            return None

    async def delete_file(self, file_id: str) -> bool:
        """
        永久刪除 Google Drive 中的檔案或資料夾。
        警告：此操作不可逆！
        :param file_id: 要刪除的檔案或資料夾的 ID。
        :return: 如果刪除成功返回 True，否則返回 False。
        """
        logger.info(f"準備永久刪除 Drive 項目 ID '{file_id}'...")
        try:
            async with self.aiogoogle as google:
                drive_v3 = await google.discover('drive', 'v3')
                # files.delete 方法不返回內容，成功則無異常
                await google.as_service_account(
                    drive_v3.files.delete(fileId=file_id)
                )
            logger.info(f"項目 ID '{file_id}' 已從 Drive 永久刪除。")
            return True
        except Exception as e:
            logger.error(f"刪除 Drive 項目 ID '{file_id}' 時發生錯誤: {e}", exc_info=True)
            return False

    async def move_file(self, file_id: str, new_parent_folder_id: str, old_parent_folder_id: str = None) -> bool:
        """
        將檔案移動到新的資料夾。
        :param file_id: 要移動的檔案 ID。
        :param new_parent_folder_id: 目標新父資料夾的 ID。
        :param old_parent_folder_id: (可選) 原始父資料夾的 ID。如果提供，將從此父資料夾中移除。
        :return: 如果移動成功返回 True，否則返回 False。
        """
        logger.info(f"準備將檔案 ID '{file_id}' 移動到資料夾 ID '{new_parent_folder_id}'...")
        try:
            async with self.aiogoogle as google:
                drive_v3 = await google.discover('drive', 'v3')

                # 移動檔案是透過更新其 'parents' 欄位實現的。
                # 這包括指定新的父資料夾並移除舊的父資料夾。
                # 為了安全起見，如果檔案可能有多個父資料夾，最好先獲取當前的父資料夾列表。
                # 但為簡化，如果提供了 old_parent_folder_id，我們直接使用它。

                update_kwargs = {
                    'fileId': file_id,
                    'addParents': new_parent_folder_id, # 添加到新的父資料夾
                    'fields': 'id, parents' # 請求回應中包含更新後的父資料夾列表以供確認
                }
                if old_parent_folder_id: # 如果提供了舊父資料夾 ID，則從中移除
                    update_kwargs['removeParents'] = old_parent_folder_id

                updated_file = await google.as_service_account(
                    drive_v3.files.update(**update_kwargs)
                )

            if new_parent_folder_id in updated_file.get('parents', []):
                logger.info(f"檔案 ID '{file_id}' 已成功移動到資料夾 ID '{new_parent_folder_id}'。")
                return True
            else:
                logger.error(f"移動檔案 ID '{file_id}' 失敗。更新後的父資料夾列表: {updated_file.get('parents')}。回應: {updated_file}")
                return False
        except Exception as e:
            logger.error(f"移動檔案 ID '{file_id}' 時發生錯誤: {e}", exc_info=True)
            return False

if __name__ == '__main__':
    import asyncio

    # 注意：此測試腳本會對您的 Google Drive 執行實際操作（創建、上傳、下載、刪除）！
    # 請務必使用一個測試用的服務帳號，並確保其權限受限。
    # 在執行前，請將 'your_service_account.json' 替換為您的服務帳號金鑰檔案的真實路徑。
    # 或者，如果您不想在根目錄下操作，可以設定 TEST_PARENT_FOLDER_ID 為一個已存在的測試資料夾 ID。
    async def test_main():
        SERVICE_ACCOUNT_FILE_FOR_TEST = 'your_service_account.json' # 【重要】請替換為您的服務帳號金鑰檔案路徑
        TEST_PARENT_FOLDER_ID = None # 【可選】設定一個測試用的父資料夾 ID，否則將在 Drive 根目錄操作

        if not os.path.exists(SERVICE_ACCOUNT_FILE_FOR_TEST):
            logger.error(f"測試需要服務帳號金鑰檔案 '{SERVICE_ACCOUNT_FILE_FOR_TEST}'。請創建此檔案並填入您的服務帳號 JSON 內容。")
            return

        try:
            drive_service = GoogleDriveService(service_account_json_path=SERVICE_ACCOUNT_FILE_FOR_TEST)
        except ValueError as e:
            logger.error(f"初始化 DriveService 失敗: {e}")
            return

        logger.info("---- 開始 GoogleDriveService 功能測試 (將對 Drive 執行實際操作) ----")

        # 1. 測試創建資料夾
        new_folder_name = f"自動測試資料夾_{int(time.time())}"
        logger.info(f"測試 create_folder: 準備創建資料夾 '{new_folder_name}'")
        created_folder_id = await drive_service.create_folder(new_folder_name, parent_folder_id=TEST_PARENT_FOLDER_ID)

        if created_folder_id:
            logger.info(f"  ✅ 成功：資料夾已創建，ID: {created_folder_id}")

            # 2. 測試列出檔案 (在父資料夾或根目錄)
            list_target_folder_name = '根目錄' if not TEST_PARENT_FOLDER_ID else f"資料夾 ID '{TEST_PARENT_FOLDER_ID}'"
            logger.info(f"測試 list_files (在 {list_target_folder_name} 中):")
            files = await drive_service.list_files(folder_id=TEST_PARENT_FOLDER_ID if TEST_PARENT_FOLDER_ID else 'root', page_size=5)
            found_our_folder = any(f['id'] == created_folder_id for f in files)
            logger.info(f"  列出檔案完成。是否找到剛創建的資料夾: {found_our_folder}")
            # for f_item in files: logger.info(f"    - {f_item.get('name')} (ID: {f_item.get('id')}, 類型: {f_item.get('mimeType')})")

            # 3. 測試上傳檔案
            test_file_content = "這是來自蒼狼 AI V2.2 GoogleDriveService 即時測試的上傳內容！"
            local_test_file_path = "temp_gdrive_upload_test.txt" # 臨時本地檔案
            with open(local_test_file_path, "w", encoding='utf-8') as f:
                f.write(test_file_content)

            logger.info(f"測試 upload_file: 準備上傳檔案 '{local_test_file_path}' 到資料夾 ID '{created_folder_id}'")
            uploaded_file_id = await drive_service.upload_file(local_test_file_path, folder_id=created_folder_id)

            if uploaded_file_id:
                logger.info(f"  ✅ 成功：檔案已上傳，ID: {uploaded_file_id}")

                # 4. 測試下載檔案
                download_destination_path = "temp_gdrive_downloaded_test.txt"
                logger.info(f"測試 download_file: 準備下載檔案 ID '{uploaded_file_id}' 到 '{download_destination_path}'")
                download_success = await drive_service.download_file(uploaded_file_id, download_destination_path)
                if download_success:
                    logger.info("  ✅ 成功：檔案已下載。")
                    with open(download_destination_path, "r", encoding='utf-8') as f:
                        downloaded_content = f.read()
                    assert downloaded_content == test_file_content, "下載的檔案內容與原始檔案內容不符！"
                    logger.info("  ✅ 下載的檔案內容驗證成功！")
                    os.remove(download_destination_path) # 清理下載的檔案
                else:
                    logger.error("  ❌ 失敗：檔案下載失敗。")

                # 5. 測試移動檔案
                target_folder_name_for_move = f"目標移動資料夾_{int(time.time())}"
                target_folder_id_for_move = await drive_service.create_folder(target_folder_name_for_move, parent_folder_id=TEST_PARENT_FOLDER_ID)
                if target_folder_id_for_move:
                    logger.info(f"  已創建用於移動測試的目標資料夾，ID: {target_folder_id_for_move}")
                    logger.info(f"測試 move_file: 準備移動檔案 ID '{uploaded_file_id}' 從 '{created_folder_id}' 到 '{target_folder_id_for_move}'")
                    move_success = await drive_service.move_file(uploaded_file_id, target_folder_id_for_move, old_parent_folder_id=created_folder_id)
                    logger.info(f"  移動操作 {'✅ 成功' if move_success else '❌ 失敗'}")

                    # 清理移動後的檔案和目標資料夾
                    logger.info(f"  準備刪除移動後的檔案 ID '{uploaded_file_id}' (在新位置)")
                    await drive_service.delete_file(uploaded_file_id)
                    logger.info(f"  準備刪除用於移動測試的目標資料夾 ID '{target_folder_id_for_move}'")
                    await drive_service.delete_file(target_folder_id_for_move)
                else:
                    logger.error("  ❌ 失敗：無法創建用於移動測試的目標資料夾。")
                    # 如果移動目標創建失敗，仍需清理已上傳的檔案 (在原位置)
                    logger.info(f"  準備刪除原始位置的上傳檔案 ID '{uploaded_file_id}'")
                    await drive_service.delete_file(uploaded_file_id)


            else: # 上傳失敗
                logger.error("  ❌ 失敗：檔案上傳失敗。")
            if os.path.exists(local_test_file_path): # 清理臨時本地檔案
                os.remove(local_test_file_path)

            # 6. 測試刪除主測試資料夾
            logger.info(f"測試 delete_file: 準備刪除主測試資料夾 ID '{created_folder_id}'")
            delete_folder_success = await drive_service.delete_file(created_folder_id)
            logger.info(f"  刪除主測試資料夾 {'✅ 成功' if delete_folder_success else '❌ 失敗'}")
        else:
            logger.error("  ❌ 失敗：初始資料夾創建失敗，後續依賴此資料夾的測試已跳過。")

        logger.info("---- GoogleDriveService 功能測試完畢 ----")

    if os.name == 'nt': # Windows 環境設定
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(test_main())
