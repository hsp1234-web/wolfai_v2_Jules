import os
import logging
import json
import time
from aiogoogle import Aiogoogle
from aiogoogle.auth.creds import ServiceAccountCreds

logger = logging.getLogger(__name__)

DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive']

class GoogleDriveService:
    def __init__(self, service_account_info: dict = None, service_account_json_path: str = None):
        self.service_account_creds = None
        init_props = {"service_name": "GoogleDriveService", "initialization_status": "starting"}

        if service_account_info:
            try:
                self.service_account_creds = ServiceAccountCreds(scopes=DRIVE_SCOPES, **service_account_info)
                logger.info(
                    "Google Drive 服務：已使用傳入的 service_account_info 初始化憑證。",
                    extra={"props": {**init_props, "method": "service_account_info_dict"}}
                )
            except Exception as e:
                logger.error(
                    f"Google Drive 服務：從 service_account_info 初始化憑證失敗: {e}", exc_info=True,
                    extra={"props": {**init_props, "method": "service_account_info_dict", "error": str(e)}}
                )
                raise ValueError(f"無效的 service_account_info: {e}")
        elif service_account_json_path:
            try:
                if not os.path.exists(service_account_json_path):
                    logger.error(
                        f"Google Drive 服務：服務帳號 JSON 檔案路徑不存在: {service_account_json_path}",
                        extra={"props": {**init_props, "method": "json_path", "path": service_account_json_path, "error": "file_not_found"}}
                    )
                    raise FileNotFoundError(f"服務帳號 JSON 檔案未找到: {service_account_json_path}")
                with open(service_account_json_path, 'r', encoding='utf-8') as f:
                    sa_info_from_file = json.load(f)
                self.service_account_creds = ServiceAccountCreds(scopes=DRIVE_SCOPES, **sa_info_from_file)
                logger.info(
                    f"Google Drive 服務：已從 JSON 檔案 {service_account_json_path} 初始化憑證。",
                    extra={"props": {**init_props, "method": "json_path", "path": service_account_json_path}}
                )
            except Exception as e:
                logger.error(
                    f"Google Drive 服務：從 JSON 檔案 {service_account_json_path} 初始化憑證失敗: {e}", exc_info=True,
                    extra={"props": {**init_props, "method": "json_path", "path": service_account_json_path, "error": str(e)}}
                )
                raise ValueError(f"從 JSON 檔案 {service_account_json_path} 初始化憑證失敗: {e}")
        else:
            logger.error(
                "Google Drive 服務：必須提供 service_account_info 或 service_account_json_path。",
                extra={"props": {**init_props, "error": "no_credentials_provided"}}
            )
            raise ValueError("未提供有效的 Google Drive 服務帳號憑證。")

        self.aiogoogle = Aiogoogle(service_account_creds=self.service_account_creds)
        logger.info("GoogleDriveService 初始化完成，Aiogoogle 客戶端已配置。", extra={"props": {**init_props, "initialization_status": "completed"}})

    async def list_files(self, folder_id: str = 'root', page_size: int = 100, fields: str = "nextPageToken, files(id, name, mimeType, modifiedTime, parents)") -> list:
        log_props = {"folder_id": folder_id, "page_size": page_size, "fields": fields, "operation": "list_files"}
        logger.info(f"正在列出 Drive 資料夾 '{folder_id}' 中的檔案...", extra={"props": {**log_props, "api_call_status": "started"}})
        all_files = []
        page_token = None
        try:
            async with self.aiogoogle as google:
                drive_v3 = await google.discover('drive', 'v3')
                while True:
                    query = f"'{folder_id}' in parents and trashed=false"
                    response = await google.as_service_account(
                        drive_v3.files.list(q=query, pageSize=min(page_size, 1000), fields=fields, pageToken=page_token, corpora="user")
                    )
                    files = response.get('files', [])
                    all_files.extend(files)
                    page_token = response.get('nextPageToken')
                    if not page_token:
                        break
            logger.info(f"成功列出資料夾 '{folder_id}' 中的 {len(all_files)} 個項目。", extra={"props": {**log_props, "api_call_status": "success", "item_count": len(all_files)}})
            return all_files
        except Exception as e:
            logger.error(f"列出 Drive 資料夾 '{folder_id}' 中的檔案時發生錯誤: {e}", exc_info=True, extra={"props": {**log_props, "api_call_status": "exception", "error": str(e)}})
            return []

    async def download_file(self, file_id: str, destination_path: str) -> bool:
        log_props = {"file_id": file_id, "destination_path": destination_path, "operation": "download_file"}
        logger.info(f"準備從 Drive 下載檔案 ID '{file_id}' 到 '{destination_path}'...", extra={"props": {**log_props, "api_call_status": "started"}})
        try:
            async with self.aiogoogle as google:
                drive_v3 = await google.discover('drive', 'v3')
                file_metadata_req = drive_v3.files.get(fileId=file_id, fields="mimeType, name")
                file_metadata = await google.as_service_account(file_metadata_req)
                file_name_for_log = file_metadata.get('name', 'UnknownName')
                log_props["file_name"] = file_name_for_log

                if file_metadata.get('mimeType') == 'application/vnd.google-apps.folder':
                    logger.error(f"錯誤：項目 ID '{file_id}' (名稱: '{file_name_for_log}') 是一個資料夾，無法直接下載。", extra={"props": {**log_props, "error": "cannot_download_folder"}})
                    return False

                dest_dir = os.path.dirname(destination_path)
                if dest_dir: # Ensure directory exists only if a path is provided (not for in-memory)
                    os.makedirs(dest_dir, exist_ok=True)

                download_req = drive_v3.files.get(fileId=file_id, alt="media", download_file=destination_path)
                response = await google.as_service_account(download_req, full_res=True)

                if response.status_code == 200:
                    logger.info(f"檔案 ID '{file_id}' ('{file_name_for_log}') 已成功下載到 '{destination_path}'。", extra={"props": {**log_props, "api_call_status": "success"}})
                    return True
                else:
                    error_content = await response.text()
                    logger.error(
                        f"下載檔案 ID '{file_id}' ('{file_name_for_log}') 失敗。狀態碼: {response.status_code}, 回應: {error_content}",
                        extra={"props": {**log_props, "api_call_status": "failure", "status_code": response.status_code, "response_text": error_content}}
                    )
                    return False
        except Exception as e:
            logger.error(f"下載檔案 ID '{file_id}' 時發生未預期錯誤: {e}", exc_info=True, extra={"props": {**log_props, "api_call_status": "exception", "error": str(e)}})
            return False

    async def upload_file(self, local_file_path: str, folder_id: str = None, file_name: str = None) -> str | None:
        drive_file_name = file_name if file_name else os.path.basename(local_file_path)
        log_props = {"local_file_path": local_file_path, "target_folder_id": folder_id, "drive_file_name": drive_file_name, "operation": "upload_file"}

        if not os.path.exists(local_file_path):
            logger.error(f"本地檔案 '{local_file_path}' 未找到，無法上傳。", extra={"props": {**log_props, "error": "local_file_not_found"}})
            return None

        logger.info(f"準備將本地檔案 '{local_file_path}' 作為 '{drive_file_name}' 上傳到 Drive 資料夾 ID '{folder_id}'...", extra={"props": {**log_props, "api_call_status": "started"}})
        file_metadata = {'name': drive_file_name}
        if folder_id:
            file_metadata['parents'] = [folder_id]
        try:
            async with self.aiogoogle as google:
                drive_v3 = await google.discover('drive', 'v3')
                response = await google.as_service_account(
                    drive_v3.files.create(upload_file=local_file_path, json=file_metadata, fields='id, name')
                )
            uploaded_file_id = response.get('id')
            if uploaded_file_id:
                logger.info(f"檔案 '{drive_file_name}' 已成功上傳到 Drive。新檔案 ID: {uploaded_file_id}", extra={"props": {**log_props, "api_call_status": "success", "uploaded_file_id": uploaded_file_id}})
                return uploaded_file_id
            else:
                logger.error(f"上傳檔案 '{drive_file_name}' 失敗。Drive API 未返回檔案 ID。回應: {response}", extra={"props": {**log_props, "api_call_status": "failure_no_id", "response": str(response)}})
                return None
        except Exception as e:
            logger.error(f"上傳檔案 '{drive_file_name}' 時發生錯誤: {e}", exc_info=True, extra={"props": {**log_props, "api_call_status": "exception", "error": str(e)}})
            return None

    async def create_folder(self, folder_name: str, parent_folder_id: str = None) -> str | None:
        log_props = {"folder_name": folder_name, "parent_folder_id": parent_folder_id, "operation": "create_folder"}
        logger.info(f"準備在父資料夾 ID '{parent_folder_id if parent_folder_id else 'root'}' 下創建資料夾 '{folder_name}'...", extra={"props": {**log_props, "api_call_status": "started"}})
        file_metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
        if parent_folder_id:
            file_metadata['parents'] = [parent_folder_id]
        try:
            async with self.aiogoogle as google:
                drive_v3 = await google.discover('drive', 'v3')
                folder = await google.as_service_account(drive_v3.files.create(json=file_metadata, fields='id, name'))
            folder_id_created = folder.get('id')
            if folder_id_created:
                logger.info(f"資料夾 '{folder_name}' (ID: {folder_id_created}) 已成功創建。", extra={"props": {**log_props, "api_call_status": "success", "created_folder_id": folder_id_created}})
                return folder_id_created
            else:
                logger.error(f"創建資料夾 '{folder_name}' 失敗。Drive API 未返回 ID。回應: {folder}", extra={"props": {**log_props, "api_call_status": "failure_no_id", "response": str(folder)}})
                return None
        except Exception as e:
            logger.error(f"創建資料夾 '{folder_name}' 時發生錯誤: {e}", exc_info=True, extra={"props": {**log_props, "api_call_status": "exception", "error": str(e)}})
            return None

    async def delete_file(self, file_id: str) -> bool:
        log_props = {"file_id": file_id, "operation": "delete_file"}
        logger.info(f"準備永久刪除 Drive 項目 ID '{file_id}'...", extra={"props": {**log_props, "api_call_status": "started"}})
        try:
            async with self.aiogoogle as google:
                drive_v3 = await google.discover('drive', 'v3')
                await google.as_service_account(drive_v3.files.delete(fileId=file_id))
            logger.info(f"項目 ID '{file_id}' 已從 Drive 永久刪除。", extra={"props": {**log_props, "api_call_status": "success"}})
            return True
        except Exception as e:
            logger.error(f"刪除 Drive 項目 ID '{file_id}' 時發生錯誤: {e}", exc_info=True, extra={"props": {**log_props, "api_call_status": "exception", "error": str(e)}})
            return False

    async def move_file(self, file_id: str, new_parent_folder_id: str, old_parent_folder_id: str = None) -> bool:
        log_props = {"file_id": file_id, "new_parent_folder_id": new_parent_folder_id, "old_parent_folder_id": old_parent_folder_id, "operation": "move_file"}
        logger.info(f"準備將檔案 ID '{file_id}' 移動到資料夾 ID '{new_parent_folder_id}'...", extra={"props": {**log_props, "api_call_status": "started"}})
        try:
            async with self.aiogoogle as google:
                drive_v3 = await google.discover('drive', 'v3')
                update_kwargs = {'fileId': file_id, 'addParents': new_parent_folder_id, 'fields': 'id, parents'}
                if old_parent_folder_id:
                    update_kwargs['removeParents'] = old_parent_folder_id
                updated_file = await google.as_service_account(drive_v3.files.update(**update_kwargs))
            if new_parent_folder_id in updated_file.get('parents', []):
                logger.info(f"檔案 ID '{file_id}' 已成功移動到資料夾 ID '{new_parent_folder_id}'。", extra={"props": {**log_props, "api_call_status": "success", "updated_parents": updated_file.get('parents')}})
                return True
            else:
                logger.error(f"移動檔案 ID '{file_id}' 失敗。更新後的父資料夾列表: {updated_file.get('parents')}。回應: {updated_file}", extra={"props": {**log_props, "api_call_status": "failure_parents_not_updated", "response": str(updated_file)}})
                return False
        except Exception as e:
            logger.error(f"移動檔案 ID '{file_id}' 時發生錯誤: {e}", exc_info=True, extra={"props": {**log_props, "api_call_status": "exception", "error": str(e)}})
            return False

# __main__ block for testing (copied, no changes needed for 'extra' here as it's for testing)
if __name__ == '__main__':
    import asyncio
    # ... (rest of __main__ block) ...
    async def test_main():
        SERVICE_ACCOUNT_FILE_FOR_TEST = 'your_service_account.json'
        TEST_PARENT_FOLDER_ID = None
        if not os.path.exists(SERVICE_ACCOUNT_FILE_FOR_TEST):
            logger.error(f"測試需要服務帳號金鑰檔案 '{SERVICE_ACCOUNT_FILE_FOR_TEST}'。請創建此檔案並填入您的服務帳號 JSON 內容。")
            return
        try:
            drive_service = GoogleDriveService(service_account_json_path=SERVICE_ACCOUNT_FILE_FOR_TEST)
        except ValueError as e:
            logger.error(f"初始化 DriveService 失敗: {e}")
            return
        logger.info("---- 開始 GoogleDriveService 功能測試 (將對 Drive 執行實際操作) ----")
        new_folder_name = f"自動測試資料夾_{int(time.time())}"
        logger.info(f"測試 create_folder: 準備創建資料夾 '{new_folder_name}'")
        created_folder_id = await drive_service.create_folder(new_folder_name, parent_folder_id=TEST_PARENT_FOLDER_ID)
        if created_folder_id:
            logger.info(f"  ✅ 成功：資料夾已創建，ID: {created_folder_id}")
            list_target_folder_name = '根目錄' if not TEST_PARENT_FOLDER_ID else f"資料夾 ID '{TEST_PARENT_FOLDER_ID}'"
            logger.info(f"測試 list_files (在 {list_target_folder_name} 中):")
            files = await drive_service.list_files(folder_id=TEST_PARENT_FOLDER_ID if TEST_PARENT_FOLDER_ID else 'root', page_size=5)
            found_our_folder = any(f['id'] == created_folder_id for f in files)
            logger.info(f"  列出檔案完成。是否找到剛創建的資料夾: {found_our_folder}")
            test_file_content = "這是來自蒼狼 AI V2.2 GoogleDriveService 即時測試的上傳內容！"
            local_test_file_path = "temp_gdrive_upload_test.txt"
            with open(local_test_file_path, "w", encoding='utf-8') as f: f.write(test_file_content)
            logger.info(f"測試 upload_file: 準備上傳檔案 '{local_test_file_path}' 到資料夾 ID '{created_folder_id}'")
            uploaded_file_id = await drive_service.upload_file(local_test_file_path, folder_id=created_folder_id)
            if uploaded_file_id:
                logger.info(f"  ✅ 成功：檔案已上傳，ID: {uploaded_file_id}")
                download_destination_path = "temp_gdrive_downloaded_test.txt"
                logger.info(f"測試 download_file: 準備下載檔案 ID '{uploaded_file_id}' 到 '{download_destination_path}'")
                download_success = await drive_service.download_file(uploaded_file_id, download_destination_path)
                if download_success:
                    logger.info("  ✅ 成功：檔案已下載。")
                    with open(download_destination_path, "r", encoding='utf-8') as f: downloaded_content = f.read()
                    assert downloaded_content == test_file_content, "下載的檔案內容與原始檔案內容不符！"
                    logger.info("  ✅ 下載的檔案內容驗證成功！")
                    os.remove(download_destination_path)
                else: logger.error("  ❌ 失敗：檔案下載失敗。")
                target_folder_name_for_move = f"目標移動資料夾_{int(time.time())}"
                target_folder_id_for_move = await drive_service.create_folder(target_folder_name_for_move, parent_folder_id=TEST_PARENT_FOLDER_ID)
                if target_folder_id_for_move:
                    logger.info(f"  已創建用於移動測試的目標資料夾，ID: {target_folder_id_for_move}")
                    logger.info(f"測試 move_file: 準備移動檔案 ID '{uploaded_file_id}' 從 '{created_folder_id}' 到 '{target_folder_id_for_move}'")
                    move_success = await drive_service.move_file(uploaded_file_id, target_folder_id_for_move, old_parent_folder_id=created_folder_id)
                    logger.info(f"  移動操作 {'✅ 成功' if move_success else '❌ 失敗'}")
                    logger.info(f"  準備刪除移動後的檔案 ID '{uploaded_file_id}' (在新位置)")
                    await drive_service.delete_file(uploaded_file_id)
                    logger.info(f"  準備刪除用於移動測試的目標資料夾 ID '{target_folder_id_for_move}'")
                    await drive_service.delete_file(target_folder_id_for_move)
                else:
                    logger.error("  ❌ 失敗：無法創建用於移動測試的目標資料夾。")
                    logger.info(f"  準備刪除原始位置的上傳檔案 ID '{uploaded_file_id}'")
                    await drive_service.delete_file(uploaded_file_id)
            else: logger.error("  ❌ 失敗：檔案上傳失敗。")
            if os.path.exists(local_test_file_path): os.remove(local_test_file_path)
            logger.info(f"測試 delete_file: 準備刪除主測試資料夾 ID '{created_folder_id}'")
            delete_folder_success = await drive_service.delete_file(created_folder_id)
            logger.info(f"  刪除主測試資料夾 {'✅ 成功' if delete_folder_success else '❌ 失敗'}")
        else: logger.error("  ❌ 失敗：初始資料夾創建失敗，後續依賴此資料夾的測試已跳過。")
        logger.info("---- GoogleDriveService 功能測試完畢 ----")
    if os.name == 'nt': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_main())
