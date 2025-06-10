import os
import logging
import json
import time
from aiogoogle import Aiogoogle
from aiogoogle.auth.creds import ServiceAccountCreds

logger = logging.getLogger(__name__)

DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive']

class GoogleDriveService:
    """
    提供與 Google Drive API 互動的服務。

    該服務封裝了使用服務帳號憑證對 Google Drive 進行操作的各種功能，
    旨在簡化應用程式中與雲端儲存相關的任務。主要職責和功能包括：

    - **憑證管理**:
        - 通過傳入的字典 (`service_account_info`) 或 JSON 檔案路徑 (`service_account_json_path`)
          來初始化和配置服務帳號憑證。
        - 使用 `aiogoogle` 函式庫與 Google API 進行非同步通訊。

    - **檔案與資料夾操作**:
        - `list_files`: 列出指定資料夾中的檔案和資料夾。
        - `download_file`: 從 Google Drive 下載檔案到本地檔案系統。
        - `upload_file`: 將本地檔案上傳到 Google Drive 的指定資料夾。
        - `create_folder`: 在 Google Drive 中創建新的資料夾。
        - `delete_file`: 永久刪除 Google Drive 中的檔案或資料夾。
        - `move_file`: 在 Google Drive 中移動檔案到不同的資料夾。

    - **錯誤處理與日誌記錄**:
        - 對 API 操作進行錯誤處理。
        - 記錄詳細的操作日誌，包括成功、失敗及異常情況，方便追蹤和調試。

    所有與 Google Drive API 的互動都是非同步的，使用 `async/await` 語法。
    該服務的目標是提供一個清晰、易用且功能完整的接口，來管理 Google Drive 上的資源。
    """
    def __init__(self, service_account_info: dict = None, service_account_json_path: str = None):
        """
        初始化 GoogleDriveService。

        該構造函數負責設置與 Google Drive API 互動所需的服務帳號憑證。
        憑證可以通過兩種方式提供（優先使用 `service_account_info`）：
        1.  `service_account_info` (dict): 一個包含服務帳號憑證完整內容的字典。
            這通常用於憑證信息動態生成或從安全儲存中提取的場景。
        2.  `service_account_json_path` (str): 指向服務帳號憑證 JSON 檔案的路徑。
            服務會讀取此檔案並解析其內容以獲取憑證。

        如果兩種方式都未提供，或者提供的憑證資訊無效（例如，檔案不存在、JSON 格式錯誤、缺少必要欄位），
        則會引發 `ValueError` 或 `FileNotFoundError`。

        成功初始化憑證後，會創建一個 `Aiogoogle` 客戶端實例，用於後續與 Drive API 的所有通訊。

        Args:
            service_account_info (dict, optional): 包含服務帳號憑證的字典。
                                                   例如：
                                                   {
                                                       "type": "service_account",
                                                       "project_id": "your-project-id",
                                                       "private_key_id": "your-private-key-id",
                                                       "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
                                                       "client_email": "your-service-account-email@your-project-id.iam.gserviceaccount.com",
                                                       "client_id": "your-client-id",
                                                       # ... 其他標準服務帳號欄位
                                                   }
                                                   預設為 None。
            service_account_json_path (str, optional): 服務帳號憑證 JSON 檔案的路徑。預設為 None。

        Raises:
            ValueError: 如果未提供任何憑證資訊，或者提供的憑證資訊無效/不完整。
            FileNotFoundError: 如果提供了 `service_account_json_path` 但檔案不存在。
        """
        self.service_account_creds = None
        init_props = {"service_name": "GoogleDriveService", "initialization_status": "starting"}

        # 優先使用直接傳入的 service_account_info 字典
        if service_account_info:
            try:
                # 使用字典內容創建 ServiceAccountCreds 對象
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
                # 重新引發異常，指明憑證資訊問題
                raise ValueError(f"無效的 service_account_info: {e}")
        # 如果未提供 service_account_info，則嘗試使用 service_account_json_path
        elif service_account_json_path:
            try:
                # 檢查 JSON 檔案是否存在
                if not os.path.exists(service_account_json_path):
                    logger.error(
                        f"Google Drive 服務：服務帳號 JSON 檔案路徑不存在: {service_account_json_path}",
                        extra={"props": {**init_props, "method": "json_path", "path": service_account_json_path, "error": "file_not_found"}}
                    )
                    raise FileNotFoundError(f"服務帳號 JSON 檔案未找到: {service_account_json_path}")
                # 讀取並解析 JSON 檔案
                with open(service_account_json_path, 'r', encoding='utf-8') as f:
                    sa_info_from_file = json.load(f)
                # 使用從檔案讀取的資訊創建 ServiceAccountCreds 對象
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
                # 重新引發異常，指明從檔案初始化憑證的問題
                raise ValueError(f"從 JSON 檔案 {service_account_json_path} 初始化憑證失敗: {e}")
        # 如果兩種憑證提供方式都未指定
        else:
            logger.error(
                "Google Drive 服務：必須提供 service_account_info 或 service_account_json_path。",
                extra={"props": {**init_props, "error": "no_credentials_provided"}}
            )
            raise ValueError("未提供有效的 Google Drive 服務帳號憑證。")

        # 使用已配置的服務帳號憑證初始化 Aiogoogle 客戶端
        self.aiogoogle = Aiogoogle(service_account_creds=self.service_account_creds)
        logger.info("GoogleDriveService 初始化完成，Aiogoogle 客戶端已配置。", extra={"props": {**init_props, "initialization_status": "completed"}})

    async def list_files(self, folder_id: str = 'root', page_size: int = 100, fields: str = "nextPageToken, files(id, name, mimeType, modifiedTime, parents)") -> list:
        """
        列出指定 Google Drive 資料夾中的檔案和子資料夾。

        此方法會向 Google Drive API 的 files.list 端點發出請求，
        使用 `q` 參數來指定父資料夾 ID 並排除已丟棄的項目 (`trashed=false`)。
        它會自動處理分頁，以獲取指定資料夾下的所有項目，直到 API 不再返回 `nextPageToken`。

        Args:
            folder_id (str, optional): 要列出內容的 Google Drive 資料夾的 ID。
                                       預設為 'root'，表示根目錄。
            page_size (int, optional): 每次 API 請求返回的項目數量上限。
                                       Google Drive API 允許的最大值通常是 1000。
                                       此方法內部會將 `page_size` 與 1000 取較小值。預設為 100。
            fields (str, optional): 指定 API 回應中應包含哪些檔案欄位的選擇器。
                                    預設為 "nextPageToken, files(id, name, mimeType, modifiedTime, parents)"，
                                    包含了分頁權杖和每個檔案/資料夾的常用元數據 (ID, 名稱, MIME 類型, 修改時間, 父資料夾列表)。
                                    有關可用欄位的更多信息，請參閱 Google Drive API 文件。

        Returns:
            list: 包含資料夾中所有檔案和子資料夾元數據字典的列表。
                  每個字典的結構由 `fields` 參數決定。
                  例如，使用預設 `fields` 時，列表中的每個項目可能如下所示：
                  {
                      "id": "file_or_folder_id",
                      "name": "File or Folder Name",
                      "mimeType": "application/vnd.google-apps.document", // 或 "application/vnd.google-apps.folder"
                      "modifiedTime": "2023-10-26T10:00:00.000Z",
                      "parents": ["parent_folder_id"]
                  }
                  如果請求過程中發生錯誤，或者資料夾為空，則返回空列表 `[]`。
        """
        log_props = {"folder_id": folder_id, "page_size": page_size, "fields": fields, "operation": "list_files"}
        logger.info(f"正在列出 Drive 資料夾 '{folder_id}' 中的檔案...", extra={"props": {**log_props, "api_call_status": "started"}})
        all_files = []
        page_token = None # 用於處理 Google Drive API 的分頁
        try:
            async with self.aiogoogle as google:
                drive_v3 = await google.discover('drive', 'v3') # 發現 Drive API v3 版本
                while True:
                    # 構建查詢語句：'folder_id' in parents 表示尋找父資料夾為 folder_id 的項目，
                    # and trashed=false 表示排除回收站中的項目。
                    query = f"'{folder_id}' in parents and trashed=false"

                    # 發起 API 請求
                    # pageSize 最大為 1000，corpora="user" 指定查詢使用者擁有的檔案
                    response = await google.as_service_account(
                        drive_v3.files.list(
                            q=query,
                            pageSize=min(page_size, 1000), # 確保 pageSize 不超過 API 限制
                            fields=fields,
                            pageToken=page_token,
                            corpora="user" # 通常用於服務帳號指定查詢哪個使用者的檔案空間，此處 "user" 指的是服務帳號自身可訪問的空間或其模擬的使用者
                        )
                    )
                    files = response.get('files', []) # 從回應中獲取檔案列表，如果沒有則為空列表
                    all_files.extend(files) # 將當前頁的檔案添加到總列表中

                    page_token = response.get('nextPageToken') # 獲取下一頁的權杖
                    if not page_token: # 如果沒有下一頁權杖，表示所有項目都已列出
                        break
            logger.info(f"成功列出資料夾 '{folder_id}' 中的 {len(all_files)} 個項目。", extra={"props": {**log_props, "api_call_status": "success", "item_count": len(all_files)}})
            return all_files
        except Exception as e:
            logger.error(f"列出 Drive 資料夾 '{folder_id}' 中的檔案時發生錯誤: {e}", exc_info=True, extra={"props": {**log_props, "api_call_status": "exception", "error": str(e)}})
            return [] # 發生錯誤時返回空列表

    async def download_file(self, file_id: str, destination_path: str) -> bool:
        """
        從 Google Drive 下載指定 ID 的檔案到本地路徑。

        此方法首先會獲取檔案的元數據 (如 MIME 類型和名稱) 以進行檢查和日誌記錄。
        如果指定的 `file_id` 對應的是一個資料夾 (MIME 類型為 'application/vnd.google-apps.folder')，
        則下載操作會被阻止並返回 False，因為資料夾本身不能作為單一檔案下載。

        對於普通檔案，它會使用 Google Drive API 的 `files.get` 方法配合 `alt="media"` 參數
        來獲取檔案內容，並將其流式傳輸到 `destination_path` 指定的本地檔案。
        如果目標資料夾不存在，此方法會嘗試創建它。

        Args:
            file_id (str): 要下載的 Google Drive 檔案的 ID。
            destination_path (str): 檔案下載到本地的完整路徑 (包含檔案名)。

        Returns:
            bool: 如果檔案成功下載並儲存到 `destination_path`，則返回 True。
                  如果在任何步驟中發生錯誤 (例如，檔案是資料夾、API 請求失敗、檔案寫入失敗)，
                  則返回 False。詳細錯誤會記錄在日誌中。
        """
        log_props = {"file_id": file_id, "destination_path": destination_path, "operation": "download_file"}
        logger.info(f"準備從 Drive 下載檔案 ID '{file_id}' 到 '{destination_path}'...", extra={"props": {**log_props, "api_call_status": "started"}})
        try:
            async with self.aiogoogle as google:
                drive_v3 = await google.discover('drive', 'v3')

                # 步驟 1: 獲取檔案元數據，特別是 MIME 類型和名稱，用於檢查和日誌
                file_metadata_req = drive_v3.files.get(fileId=file_id, fields="mimeType, name")
                file_metadata = await google.as_service_account(file_metadata_req)
                file_name_for_log = file_metadata.get('name', 'UnknownName') # 用於日誌的檔案名
                log_props["file_name"] = file_name_for_log

                # 步驟 2: 檢查是否為資料夾，資料夾不能直接下載
                if file_metadata.get('mimeType') == 'application/vnd.google-apps.folder':
                    logger.error(f"錯誤：項目 ID '{file_id}' (名稱: '{file_name_for_log}') 是一個資料夾，無法直接下載。", extra={"props": {**log_props, "error": "cannot_download_folder"}})
                    return False

                # 步驟 3: 確保目標本地資料夾存在
                dest_dir = os.path.dirname(destination_path)
                if dest_dir: # 僅當 destination_path 包含目錄時才創建
                    os.makedirs(dest_dir, exist_ok=True) # 如果資料夾已存在，exist_ok=True 會避免拋出錯誤

                # 步驟 4: 準備並執行檔案下載請求
                # `alt="media"` 表示我們要下載檔案內容
                # `download_file=destination_path` 讓 aiogoogle 直接將回應流寫入到指定檔案
                download_req = drive_v3.files.get(fileId=file_id, alt="media", download_file=destination_path)
                # `full_res=True` 讓我們可以訪問完整的 HTTP 回應對象，包括狀態碼
                response = await google.as_service_account(download_req, full_res=True)

                # 步驟 5: 檢查 HTTP 狀態碼以確認下載是否成功
                if response.status_code == 200:
                    logger.info(f"檔案 ID '{file_id}' ('{file_name_for_log}') 已成功下載到 '{destination_path}'。", extra={"props": {**log_props, "api_call_status": "success"}})
                    return True
                else:
                    # 如果狀態碼不是 200，記錄錯誤詳情
                    error_content = await response.text() # 獲取錯誤回應的文本內容
                    logger.error(
                        f"下載檔案 ID '{file_id}' ('{file_name_for_log}') 失敗。狀態碼: {response.status_code}, 回應: {error_content}",
                        extra={"props": {**log_props, "api_call_status": "failure", "status_code": response.status_code, "response_text": error_content}}
                    )
                    return False
        except Exception as e: # 捕獲其他潛在錯誤，例如網路問題或 aiogoogle 內部錯誤
            logger.error(f"下載檔案 ID '{file_id}' 時發生未預期錯誤: {e}", exc_info=True, extra={"props": {**log_props, "api_call_status": "exception", "error": str(e)}})
            return False

    async def upload_file(self, local_file_path: str, folder_id: str = None, file_name: str = None) -> str | None:
        """
        將本地檔案上傳到指定的 Google Drive 資料夾。

        此方法會執行以下操作：
        1. 檢查本地檔案是否存在，如果不存在則記錄錯誤並返回 None。
        2. 確定在 Google Drive 中儲存的檔案名。如果提供了 `file_name` 參數，則使用它；
           否則，使用本地檔案的原始名稱。
        3. 構造檔案元數據，包括檔案名和父資料夾 ID (如果提供)。
        4. 使用 Google Drive API 的 `files.create` 方法上傳檔案。
           `aiogoogle` 會自動處理 MIME 類型檢測和實際的檔案內容傳輸。
           (注意: `aiogoogle` 預設使用簡單上傳。對於非常大的檔案，可能需要考慮可續傳上傳，
           但这需要更複雜的實現，目前此方法未直接支持。)
        5. 請求 API 在回應中返回新創建檔案的 ID 和名稱。

        Args:
            local_file_path (str): 要上傳的本地檔案的完整路徑。
            folder_id (str, optional): 要將檔案上傳到的目標 Google Drive 資料夾的 ID。
                                       如果為 None，檔案將上傳到使用者的 Drive 根目錄。預設為 None。
            file_name (str, optional): 在 Google Drive 中儲存檔案時使用的名稱。
                                       如果為 None，則使用 `local_file_path` 中的檔案名。預設為 None。

        Returns:
            Optional[str]: 如果檔案成功上傳，返回在 Google Drive 中新創建檔案的 ID。
                           如果上傳失敗 (例如，本地檔案不存在、API 請求錯誤、API 未返回 ID)，
                           則返回 None。詳細錯誤會記錄在日誌中。
        """
        # 確定最終在 Drive 上顯示的檔案名
        drive_file_name = file_name if file_name else os.path.basename(local_file_path)
        log_props = {"local_file_path": local_file_path, "target_folder_id": folder_id, "drive_file_name": drive_file_name, "operation": "upload_file"}

        # 步驟 1: 檢查本地檔案是否存在
        if not os.path.exists(local_file_path):
            logger.error(f"本地檔案 '{local_file_path}' 未找到，無法上傳。", extra={"props": {**log_props, "error": "local_file_not_found"}})
            return None

        logger.info(f"準備將本地檔案 '{local_file_path}' 作為 '{drive_file_name}' 上傳到 Drive 資料夾 ID '{folder_id}'...", extra={"props": {**log_props, "api_call_status": "started"}})

        # 步驟 2: 準備檔案元數據
        file_metadata = {'name': drive_file_name}
        if folder_id: # 如果指定了目標資料夾，將其 ID 添加到父項目列表中
            file_metadata['parents'] = [folder_id]

        try:
            async with self.aiogoogle as google:
                drive_v3 = await google.discover('drive', 'v3')
                # 步驟 3: 執行上傳操作
                # `upload_file` 參數指向本地檔案路徑，aiogoogle 會處理檔案讀取和傳輸
                # `json` 參數包含檔案的元數據
                # `fields` 參數指定我們希望從 API 回應中獲取哪些關於新檔案的資訊
                response = await google.as_service_account(
                    drive_v3.files.create(upload_file=local_file_path, json=file_metadata, fields='id, name')
                )

            # 步驟 4: 檢查回應並提取檔案 ID
            uploaded_file_id = response.get('id')
            if uploaded_file_id:
                logger.info(f"檔案 '{drive_file_name}' 已成功上傳到 Drive。新檔案 ID: {uploaded_file_id}", extra={"props": {**log_props, "api_call_status": "success", "uploaded_file_id": uploaded_file_id}})
                return uploaded_file_id
            else:
                # 雖然不太可能在成功請求後沒有 ID，但作為預防措施進行檢查
                logger.error(f"上傳檔案 '{drive_file_name}' 失敗。Drive API 未返回檔案 ID。回應: {response}", extra={"props": {**log_props, "api_call_status": "failure_no_id", "response": str(response)}})
                return None
        except Exception as e: # 捕獲 API 請求錯誤或其他異常
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
        """
        將 Google Drive 中的檔案或資料夾移動到新的父資料夾。

        此方法使用 Google Drive API 的 `files.update` 方法來更改檔案的父資料夾。
        它通過 `addParents` 參數指定新的父資料夾 ID，並可選地通過 `removeParents`
        參數指定要移除的舊父資料夾 ID。

        注意：Google Drive 允許一個檔案存在於多個父資料夾中。此方法旨在將檔案
        “移動”到一個新的位置。如果提供了 `old_parent_folder_id`，它會嘗試從該舊位置移除。
        如果不提供 `old_parent_folder_id`，檔案將被添加到新的父資料夾，但可能仍保留在
        其原有的其他父資料夾中（如果它存在於多個位置）。

        Args:
            file_id (str): 要移動的檔案或資料夾的 ID。
            new_parent_folder_id (str): 目標父資料夾的 ID，檔案將被移動到此資料夾下。
            old_parent_folder_id (str, optional): 原始父資料夾的 ID。如果提供此參數，
                                                  方法會嘗試從這個舊的父資料夾中移除該檔案。
                                                  如果檔案僅存在於一個父資料夾下，建議提供此參數
                                                  以完成真正的“移動”操作。預設為 None。

        Returns:
            bool: 如果檔案成功更新其父資料夾列表以包含新的父資料夾，則返回 True。
                  如果 API 請求失敗，或者更新後的回應未確認新的父資料夾關係，則返回 False。
                  詳細錯誤會記錄在日誌中。
        """
        log_props = {"file_id": file_id, "new_parent_folder_id": new_parent_folder_id, "old_parent_folder_id": old_parent_folder_id, "operation": "move_file"}
        logger.info(f"準備將檔案 ID '{file_id}' 移動到資料夾 ID '{new_parent_folder_id}'...", extra={"props": {**log_props, "api_call_status": "started"}})

        try:
            async with self.aiogoogle as google:
                drive_v3 = await google.discover('drive', 'v3')

                # 準備 files.update 方法的參數
                update_kwargs = {
                    'fileId': file_id,
                    'addParents': new_parent_folder_id, # 指定要添加的新父資料夾
                    'fields': 'id, parents' # 要求 API 返回更新後的檔案 ID 和父資料夾列表，以便驗證
                }
                if old_parent_folder_id:
                    # 如果提供了舊父資料夾 ID，則添加到參數中以移除
                    update_kwargs['removeParents'] = old_parent_folder_id

                # 執行更新操作
                updated_file = await google.as_service_account(drive_v3.files.update(**update_kwargs))

            # 驗證更新是否成功：檢查新的父資料夾 ID 是否出現在返回的父資料夾列表中
            if new_parent_folder_id in updated_file.get('parents', []):
                logger.info(f"檔案 ID '{file_id}' 已成功移動到資料夾 ID '{new_parent_folder_id}'。", extra={"props": {**log_props, "api_call_status": "success", "updated_parents": updated_file.get('parents')}})
                return True
            else:
                # 如果 API 成功執行但父資料夾列表未按預期更新，記錄錯誤
                logger.error(f"移動檔案 ID '{file_id}' 失敗。更新後的父資料夾列表: {updated_file.get('parents')}。回應: {updated_file}", extra={"props": {**log_props, "api_call_status": "failure_parents_not_updated", "response": str(updated_file)}})
                return False
        except Exception as e: # 捕獲 API 請求錯誤或其他異常
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
