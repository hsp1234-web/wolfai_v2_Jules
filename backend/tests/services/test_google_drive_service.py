# -*- coding: utf-8 -*-
import pytest
import json
import os
from unittest.mock import MagicMock, AsyncMock, patch

from backend.services.google_drive_service import GoogleDriveService, DRIVE_SCOPES
from aiogoogle.auth.creds import ServiceAccountCreds

# 可重用的服務帳號資訊字典
VALID_SERVICE_ACCOUNT_INFO = {
    "type": "service_account",
    "project_id": "test-project",
    "private_key_id": "test_key_id",
    "private_key": "-----BEGIN PRIVATE KEY-----\nFAKEKEY\n-----END PRIVATE KEY-----\n",
    "client_email": "test@test-project.iam.gserviceaccount.com",
    "client_id": "1234567890",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/test%40test-project.iam.gserviceaccount.com"
}

@pytest.fixture
def valid_service_account_file(tmp_path):
    """創建一個有效的模擬服務帳號 JSON 檔案，並返回其路徑。"""
    file_path = tmp_path / "service_account.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(VALID_SERVICE_ACCOUNT_INFO, f)
    return str(file_path)

@pytest.fixture
def invalid_service_account_file_bad_json(tmp_path):
    """創建一個 JSON 格式無效的模擬服務帳號檔案。"""
    file_path = tmp_path / "invalid_service_account.json"
    file_path.write_text("這不是有效的JSON {")
    return str(file_path)

# --- __init__ 測試 ---

def test_init_no_credentials_raises_value_error():
    """
    測試當 service_account_info 和 service_account_json_path 都未提供時，
    GoogleDriveService 的 __init__ 是否如預期拋出 ValueError。
    """
    with pytest.raises(ValueError, match="未提供有效的 Google Drive 服務帳號憑證。"):
        GoogleDriveService(service_account_info=None, service_account_json_path=None)

def test_init_json_path_not_found_raises_file_not_found_error(tmp_path):
    """
    測試當提供的 service_account_json_path 檔案不存在時，
    GoogleDriveService 的 __init__ 是否如預期拋出 FileNotFoundError。
    """
    non_existent_path = tmp_path / "non_existent_sa.json"
    with pytest.raises(FileNotFoundError, match=f"服務帳號 JSON 檔案未找到: {non_existent_path}"):
        GoogleDriveService(service_account_json_path=str(non_existent_path))

def test_init_invalid_json_content_raises_value_error(invalid_service_account_file_bad_json: str):
    """
    測試當提供的服務帳號 JSON 檔案內容無效時，
    GoogleDriveService 的 __init__ 是否如預期拋出 ValueError。
    """
    with pytest.raises(ValueError, match=f"從 JSON 檔案 {invalid_service_account_file_bad_json} 初始化憑證失敗"):
        GoogleDriveService(service_account_json_path=invalid_service_account_file_bad_json)

@patch('aiogoogle.Aiogoogle') # Mock Aiogoogle 以避免實際的網路調用或憑證驗證
@patch('aiogoogle.auth.creds.ServiceAccountCreds') # Mock ServiceAccountCreds
def test_init_success_with_service_account_info(mock_sa_creds, mock_aiogoogle_constructor):
    """
    測試使用有效的 service_account_info 字典成功初始化 GoogleDriveService。
    """
    service = GoogleDriveService(service_account_info=VALID_SERVICE_ACCOUNT_INFO)

    mock_sa_creds.assert_called_once_with(scopes=DRIVE_SCOPES, **VALID_SERVICE_ACCOUNT_INFO)
    mock_aiogoogle_constructor.assert_called_once_with(service_account_creds=mock_sa_creds.return_value)
    assert service.service_account_creds is not None
    assert service.aiogoogle is not None

@patch('aiogoogle.Aiogoogle')
@patch('aiogoogle.auth.creds.ServiceAccountCreds')
def test_init_success_with_json_path(mock_sa_creds, mock_aiogoogle_constructor, valid_service_account_file: str):
    """
    測試使用有效的服務帳號 JSON 檔案路徑成功初始化 GoogleDriveService。
    """
    service = GoogleDriveService(service_account_json_path=valid_service_account_file)

    # 驗證 ServiceAccountCreds 是否以從檔案讀取的內容被調用
    # 我們需要比較傳遞給 ServiceAccountCreds 的 kwargs 是否與 VALID_SERVICE_ACCOUNT_INFO 一致
    # mock_sa_creds.assert_called_once_with(scopes=DRIVE_SCOPES, **VALID_SERVICE_ACCOUNT_INFO) # 這樣直接比較可能因為實例不同而失敗

    # 檢查 ServiceAccountCreds 是否被調用，以及 scopes 是否正確
    called_args, called_kwargs = mock_sa_creds.call_args
    assert called_kwargs['scopes'] == DRIVE_SCOPES
    # 檢查傳遞給 ServiceAccountCreds 的其他參數是否與檔案內容匹配
    for key, value in VALID_SERVICE_ACCOUNT_INFO.items():
        assert called_kwargs[key] == value

    mock_aiogoogle_constructor.assert_called_once_with(service_account_creds=mock_sa_creds.return_value)
    assert service.service_account_creds is not None
    assert service.aiogoogle is not None

# --- Mock Fixture for Aiogoogle and Drive API calls ---
@pytest.fixture
def mock_aiogoogle_service_account(mocker):
    """
    一個核心的 mocker fixture，用於模擬 Aiogoogle 客戶端及其 as_service_account 調用鏈。
    返回一個 mock 過的 drive_v3 API 對象，其上的方法 (files, etc.) 都是 AsyncMock。
    """
    mock_google = MagicMock(spec=Aiogoogle) # Mock the Aiogoogle instance itself
    mock_drive_v3_api = MagicMock() # This will represent the discovered drive_v3 API

    # Mock the discover method
    mock_google.discover = AsyncMock(return_value=mock_drive_v3_api)

    # Mock the as_service_account context manager and its result
    # as_service_account is typically used as an async context manager
    # but here we are mocking what `google.as_service_account(drive_v3.files.list(...))` would resolve to.
    # So, we make as_service_account an AsyncMock that returns a predefined response or another mock.
    mock_as_service_account_response = AsyncMock()
    mock_google.as_service_account = mock_as_service_account_response

    # Mock specific API methods on drive_v3.files (which itself needs to be a mock)
    mock_drive_v3_api.files = MagicMock()
    mock_drive_v3_api.files.list = AsyncMock()
    mock_drive_v3_api.files.get = AsyncMock()
    mock_drive_v3_api.files.create = AsyncMock()
    mock_drive_v3_api.files.update = AsyncMock()
    mock_drive_v3_api.files.delete = AsyncMock()

    # Patch the Aiogoogle constructor to return our main mock_google instance
    mocker.patch('backend.services.google_drive_service.Aiogoogle', return_value=mock_google)

    return mock_google, mock_drive_v3_api # Return both for finer control if needed


@pytest.fixture
def valid_service(mock_aiogoogle_service_account):
    """
    提供一個已成功初始化並 mock 了 Aiogoogle 的 GoogleDriveService 實例。
    """
    # 使用 service_account_info 初始化，以避免檔案系統依賴
    # Aiogoogle 已經被 mock_aiogoogle_service_account mock掉了，所以這裡的憑證內容僅用於滿足構造函數
    service = GoogleDriveService(service_account_info=VALID_SERVICE_ACCOUNT_INFO)
    return service

# 後續將在此處添加其他方法的測試案例...
# 例如: test_list_files_success_no_pagination, test_download_file_is_folder_error etc.

# --- list_files 測試 ---

@pytest.mark.asyncio
async def test_list_files_success_no_pagination(valid_service: GoogleDriveService, mock_aiogoogle_service_account):
    """
    測試 list_files 方法：API 成功返回檔案列表，無需分頁。
    """
    mock_google, mock_drive_v3_api = mock_aiogoogle_service_account

    # 模擬 drive_v3.files.list().execute() 的成功回應 (在 aiogoogle 中是直接 await)
    expected_files = [{"id": "file1", "name": "報告A.pdf"}, {"id": "folder1", "name": "圖片資料夾"}]
    api_response = {"files": expected_files} # nextPageToken 未提供，表示只有一頁

    # 讓 as_service_account (代表已執行的請求) 返回此模擬回應
    # 因為 list_files 內部會直接 await google.as_service_account(drive_v3.files.list(...))
    mock_google.as_service_account.return_value = api_response

    folder_id_to_list = "test_folder_id_123"
    files = await valid_service.list_files(folder_id=folder_id_to_list)

    assert files == expected_files
    # 驗證 drive_v3.files.list 是否以正確參數被調用
    mock_drive_v3_api.files.list.assert_called_once_with(
        q=f"'{folder_id_to_list}' in parents and trashed=false",
        pageSize=100, # 預設 pageSize
        fields="nextPageToken, files(id, name, mimeType, modifiedTime, parents)", # 預設 fields
        pageToken=None,
        corpora="user"
    )
    mock_google.as_service_account.assert_called_once_with(mock_drive_v3_api.files.list.return_value)


@pytest.mark.asyncio
async def test_list_files_success_with_pagination(valid_service: GoogleDriveService, mock_aiogoogle_service_account):
    """
    測試 list_files 方法：API 成功返回檔案列表，並處理分頁。
    """
    mock_google, mock_drive_v3_api = mock_aiogoogle_service_account

    # 模擬分頁回應
    page1_files = [{"id": "file1", "name": "檔案1.txt"}]
    page2_files = [{"id": "file2", "name": "檔案2.docx"}]

    # as_service_account 會被調用兩次
    # 第一次返回 page1 和 nextPageToken
    # 第二次返回 page2，無 nextPageToken
    mock_google.as_service_account.side_effect = [
        {"files": page1_files, "nextPageToken": "token_page_2"},
        {"files": page2_files} # 最後一頁，沒有 nextPageToken
    ]

    all_files = await valid_service.list_files(folder_id="paginated_folder", page_size=1) # page_size=1 強制分頁

    assert len(all_files) == 2
    assert all_files == page1_files + page2_files
    assert mock_drive_v3_api.files.list.call_count == 2

    # 檢查第一次調用
    call_args_list = mock_drive_v3_api.files.list.call_args_list
    assert call_args_list[0][1]['pageToken'] is None # 第一次pageToken為None
    assert call_args_list[0][1]['pageSize'] == 1
    # 檢查第二次調用
    assert call_args_list[1][1]['pageToken'] == "token_page_2"
    assert call_args_list[1][1]['pageSize'] == 1

    assert mock_google.as_service_account.call_count == 2


@pytest.mark.asyncio
async def test_list_files_empty_result(valid_service: GoogleDriveService, mock_aiogoogle_service_account):
    """
    測試 list_files 方法：API 返回空檔案列表。
    """
    mock_google, mock_drive_v3_api = mock_aiogoogle_service_account
    mock_google.as_service_account.return_value = {"files": []} # API 返回空列表

    files = await valid_service.list_files(folder_id="empty_folder")

    assert files == []
    mock_drive_v3_api.files.list.assert_called_once()


@pytest.mark.asyncio
async def test_list_files_api_call_exception(valid_service: GoogleDriveService, mock_aiogoogle_service_account):
    """
    測試 list_files 方法：當 API 呼叫拋出異常時，應返回空列表。
    """
    mock_google, mock_drive_v3_api = mock_aiogoogle_service_account

    # 模擬 API 調用 (即 as_service_account 的結果) 拋出異常
    mock_google.as_service_account.side_effect = Exception("模擬 API 連線錯誤")

    files = await valid_service.list_files(folder_id="folder_with_error")

    assert files == [] # 預期在異常時返回空列表
    mock_drive_v3_api.files.list.assert_called_once() # 嘗試調用了 list
    mock_google.as_service_account.assert_called_once() # 嘗試執行請求

# --- download_file 測試 ---

@pytest.mark.asyncio
async def test_download_file_success(valid_service: GoogleDriveService, mock_aiogoogle_service_account, tmp_path):
    """
    測試 download_file 方法：成功下載檔案。
    """
    mock_google, mock_drive_v3_api = mock_aiogoogle_service_account
    file_id = "test_file_id_download"
    file_name = "test_document.pdf"
    destination_path = tmp_path / file_name

    # 模擬元數據獲取
    mock_metadata_response = {"mimeType": "application/pdf", "name": file_name}
    # 模擬下載請求成功 (aiogoogle 的 download_file 會直接寫入檔案，所以 files.get(alt="media") 的 as_service_account 返回的 response 需要有 status_code)
    mock_download_response = MagicMock()
    mock_download_response.status_code = 200

    # as_service_account 第一次調用用於元數據，第二次用於下載
    mock_google.as_service_account.side_effect = [mock_metadata_response, mock_download_response]

    success = await valid_service.download_file(file_id, str(destination_path))

    assert success is True
    # 驗證 get 元數據的調用
    mock_drive_v3_api.files.get.assert_any_call(fileId=file_id, fields="mimeType, name")
    # 驗證 get 媒體內容的調用
    mock_drive_v3_api.files.get.assert_any_call(fileId=file_id, alt="media", download_file=str(destination_path))
    assert mock_google.as_service_account.call_count == 2
    # 實際檔案是否被 mock "寫入" 取決於 aiogoogle 的 download_file 參數如何與 mock 互動
    # 在此測試中，我們主要關心的是否返回 True 以及 API 是否被正確調用。
    # 如果 download_file 參數使得 aiogoogle 嘗試打開文件句柄，可能需要 mock open。
    # 但通常 mock HTTP 層面的 status_code == 200 即可。

@pytest.mark.asyncio
async def test_download_file_is_folder_error(valid_service: GoogleDriveService, mock_aiogoogle_service_account, tmp_path):
    """
    測試 download_file 方法：嘗試下載一個資料夾時，應返回 False。
    """
    mock_google, mock_drive_v3_api = mock_aiogoogle_service_account
    folder_id = "test_folder_id_download_error"
    folder_name = "My Documents"
    destination_path = tmp_path / folder_name

    mock_metadata_response = {"mimeType": "application/vnd.google-apps.folder", "name": folder_name}
    mock_google.as_service_account.return_value = mock_metadata_response # 僅調用一次獲取元數據

    success = await valid_service.download_file(folder_id, str(destination_path))

    assert success is False
    mock_drive_v3_api.files.get.assert_called_once_with(fileId=folder_id, fields="mimeType, name")
    mock_google.as_service_account.assert_called_once() # 只應調用元數據獲取

@pytest.mark.asyncio
async def test_download_file_metadata_fetch_fails(valid_service: GoogleDriveService, mock_aiogoogle_service_account, tmp_path):
    """
    測試 download_file 方法：當獲取檔案元數據失敗時，應返回 False。
    """
    mock_google, mock_drive_v3_api = mock_aiogoogle_service_account
    file_id = "metadata_fail_id"
    destination_path = tmp_path / "metadata_fail_doc.txt"

    # 模擬獲取元數據時 API 拋出異常
    mock_google.as_service_account.side_effect = Exception("模擬獲取元數據失敗")

    success = await valid_service.download_file(file_id, str(destination_path))

    assert success is False
    mock_drive_v3_api.files.get.assert_called_once_with(fileId=file_id, fields="mimeType, name")
    mock_google.as_service_account.assert_called_once()

@pytest.mark.asyncio
async def test_download_file_media_download_fails_non_200(valid_service: GoogleDriveService, mock_aiogoogle_service_account, tmp_path):
    """
    測試 download_file 方法：下載媒體內容時 API 返回非 200 狀態碼。
    """
    mock_google, mock_drive_v3_api = mock_aiogoogle_service_account
    file_id = "media_fail_id"
    file_name = "media_fail_doc.txt"
    destination_path = tmp_path / file_name

    mock_metadata_response = {"mimeType": "text/plain", "name": file_name}
    mock_download_response = MagicMock()
    mock_download_response.status_code = 500 # 模擬伺服器錯誤
    mock_download_response.text = AsyncMock(return_value="Internal Server Error") # 模擬錯誤文本

    mock_google.as_service_account.side_effect = [mock_metadata_response, mock_download_response]

    success = await valid_service.download_file(file_id, str(destination_path))

    assert success is False
    assert mock_google.as_service_account.call_count == 2


@pytest.mark.asyncio
async def test_download_file_media_download_exception(valid_service: GoogleDriveService, mock_aiogoogle_service_account, tmp_path):
    """
    測試 download_file 方法：下載媒體內容時 API 拋出異常。
    """
    mock_google, mock_drive_v3_api = mock_aiogoogle_service_account
    file_id = "media_exception_id"
    file_name = "media_exception_doc.txt"
    destination_path = tmp_path / file_name

    mock_metadata_response = {"mimeType": "text/plain", "name": file_name}

    # 第一次調用 (元數據) 成功，第二次調用 (下載) 拋出異常
    mock_google.as_service_account.side_effect = [
        mock_metadata_response,
        Exception("模擬下載媒體內容時的網路錯誤")
    ]

    success = await valid_service.download_file(file_id, str(destination_path))

    assert success is False
    assert mock_google.as_service_account.call_count == 2 # 兩次都被嘗試了

@pytest.mark.asyncio
async def test_download_file_local_write_permission_error(valid_service: GoogleDriveService, mock_aiogoogle_service_account, tmp_path, mocker):
    """
    測試 download_file 方法：當本地目錄創建失敗 (例如權限問題)。
    """
    mock_google, mock_drive_v3_api = mock_aiogoogle_service_account
    file_id = "local_write_fail_id"
    file_name = "local_write_fail.txt"
    # 使用一個 tmp_path 下的子目錄，我們將使其創建失敗
    problematic_dest_dir = tmp_path / "restricted_subdir"
    destination_path = problematic_dest_dir / file_name

    mock_metadata_response = {"mimeType": "text/plain", "name": file_name}
    mock_google.as_service_account.return_value = mock_metadata_response # 第一次元數據調用

    # 模擬 os.makedirs 拋出 OSError (例如權限不足)
    mocker.patch('os.makedirs', side_effect=OSError("模擬目錄創建失敗"))

    success = await valid_service.download_file(file_id, str(destination_path))

    assert success is False
    # 確保 os.makedirs 被調用（如果 dest_dir 非空）
    if os.path.dirname(destination_path): # 只有在路徑包含目錄時才會調用 makedirs
        os.makedirs.assert_called_once_with(os.path.dirname(destination_path), exist_ok=True)
    # 即使 makedirs 失敗，後續的下載請求也不應發出
    # 在此實現中，makedirs 失敗會直接拋出異常，然後被 download_file 中的頂層 except 捕獲
    # 所以 as_service_account 只會因為元數據被調用一次
    mock_google.as_service_account.assert_called_once()

# --- upload_file 測試 ---

@pytest.mark.asyncio
async def test_upload_file_success(valid_service: GoogleDriveService, mock_aiogoogle_service_account, tmp_path):
    """
    測試 upload_file 方法：成功上傳檔案。
    """
    mock_google, mock_drive_v3_api = mock_aiogoogle_service_account
    local_file_content = "這是測試上傳的檔案內容。"
    local_file = tmp_path / "upload_me.txt"
    local_file.write_text(local_file_content, encoding="utf-8")

    target_folder_id = "target_folder_123"
    drive_file_name = "uploaded_file_on_drive.txt"
    expected_uploaded_file_id = "new_drive_file_id_abc"

    # 模擬 files.create().execute() 的成功回應
    mock_google.as_service_account.return_value = {"id": expected_uploaded_file_id, "name": drive_file_name}

    uploaded_file_id = await valid_service.upload_file(
        local_file_path=str(local_file),
        folder_id=target_folder_id,
        file_name=drive_file_name
    )

    assert uploaded_file_id == expected_uploaded_file_id
    # 驗證 files.create 是否以正確參數被調用
    # mock_drive_v3_api.files.create.assert_called_once() # 這樣不夠精確
    # 我們需要檢查傳遞給 create 的 upload_file 和 json/body 參數
    called_args, called_kwargs = mock_drive_v3_api.files.create.call_args
    assert called_kwargs['upload_file'] == str(local_file)
    assert called_kwargs['json']['name'] == drive_file_name
    assert called_kwargs['json']['parents'] == [target_folder_id]
    assert called_kwargs['fields'] == 'id, name'
    mock_google.as_service_account.assert_called_once_with(mock_drive_v3_api.files.create.return_value)


@pytest.mark.asyncio
async def test_upload_file_local_file_not_exists(valid_service: GoogleDriveService):
    """
    測試 upload_file 方法：當本地檔案不存在時，應返回 None。
    """
    non_existent_local_file = "/tmp/this/path/surely/does/not/exist/file.txt"
    uploaded_file_id = await valid_service.upload_file(
        local_file_path=non_existent_local_file,
        folder_id="any_folder_id"
    )
    assert uploaded_file_id is None

@pytest.mark.asyncio
async def test_upload_file_api_call_exception(valid_service: GoogleDriveService, mock_aiogoogle_service_account, tmp_path):
    """
    測試 upload_file 方法：當 API 呼叫 files.create 拋出異常時，應返回 None。
    """
    mock_google, _ = mock_aiogoogle_service_account # mock_drive_v3_api 不需要直接驗證
    local_file = tmp_path / "upload_exception.txt"
    local_file.write_text("content", encoding="utf-8")

    # 模擬 API 調用拋出異常
    mock_google.as_service_account.side_effect = Exception("模擬 API 上傳錯誤")

    uploaded_file_id = await valid_service.upload_file(str(local_file), "folder_id")

    assert uploaded_file_id is None
    mock_google.as_service_account.assert_called_once() # 驗證確實嘗試了API調用

@pytest.mark.asyncio
async def test_upload_file_api_returns_no_id(valid_service: GoogleDriveService, mock_aiogoogle_service_account, tmp_path):
    """
    測試 upload_file 方法：當 API 呼叫成功但未返回檔案 ID 時，應返回 None。
    """
    mock_google, _ = mock_aiogoogle_service_account
    local_file = tmp_path / "upload_no_id.txt"
    local_file.write_text("content", encoding="utf-8")

    # 模擬 API 回應中沒有 'id'
    mock_google.as_service_account.return_value = {"name": "uploaded_file_on_drive.txt"} #缺少 id

    uploaded_file_id = await valid_service.upload_file(str(local_file), "folder_id")

    assert uploaded_file_id is None
    mock_google.as_service_account.assert_called_once()

# --- create_folder 測試 ---

@pytest.mark.asyncio
async def test_create_folder_success(valid_service: GoogleDriveService, mock_aiogoogle_service_account):
    """
    測試 create_folder 方法：成功創建資料夾。
    """
    mock_google, mock_drive_v3_api = mock_aiogoogle_service_account
    folder_name = "新測試資料夾"
    parent_folder_id = "parent_id_123"
    expected_folder_id = "new_folder_id_xyz"

    mock_google.as_service_account.return_value = {"id": expected_folder_id, "name": folder_name}

    created_folder_id = await valid_service.create_folder(folder_name, parent_folder_id=parent_folder_id)

    assert created_folder_id == expected_folder_id
    called_args, called_kwargs = mock_drive_v3_api.files.create.call_args
    assert called_kwargs['json']['name'] == folder_name
    assert called_kwargs['json']['mimeType'] == 'application/vnd.google-apps.folder'
    assert called_kwargs['json']['parents'] == [parent_folder_id]
    assert called_kwargs['fields'] == 'id, name'
    mock_google.as_service_account.assert_called_once_with(mock_drive_v3_api.files.create.return_value)

@pytest.mark.asyncio
async def test_create_folder_api_call_exception(valid_service: GoogleDriveService, mock_aiogoogle_service_account):
    """
    測試 create_folder 方法：當 API 呼叫 files.create 拋出異常時，應返回 None。
    """
    mock_google, _ = mock_aiogoogle_service_account
    mock_google.as_service_account.side_effect = Exception("模擬 API 創建資料夾錯誤")

    created_folder_id = await valid_service.create_folder("錯誤資料夾", "parent_id")
    assert created_folder_id is None
    mock_google.as_service_account.assert_called_once()

@pytest.mark.asyncio
async def test_create_folder_api_returns_no_id(valid_service: GoogleDriveService, mock_aiogoogle_service_account):
    """
    測試 create_folder 方法：當 API 呼叫成功但未返回資料夾 ID 時，應返回 None。
    """
    mock_google, _ = mock_aiogoogle_service_account
    mock_google.as_service_account.return_value = {"name": "無ID資料夾"} #缺少 id

    created_folder_id = await valid_service.create_folder("無ID資料夾", "parent_id")
    assert created_folder_id is None
    mock_google.as_service_account.assert_called_once()


# --- move_file 測試 ---

@pytest.mark.asyncio
async def test_move_file_success(valid_service: GoogleDriveService, mock_aiogoogle_service_account):
    """
    測試 move_file 方法：成功移動檔案。
    """
    mock_google, mock_drive_v3_api = mock_aiogoogle_service_account
    file_id_to_move = "file_to_move_id"
    new_parent_id = "new_parent_folder_id"
    old_parent_id = "old_parent_folder_id"

    # 模擬 files.update().execute() 的成功回應
    mock_google.as_service_account.return_value = {"id": file_id_to_move, "parents": [new_parent_id]}

    success = await valid_service.move_file(file_id_to_move, new_parent_id, old_parent_folder_id=old_parent_id)

    assert success is True
    called_args, called_kwargs = mock_drive_v3_api.files.update.call_args
    assert called_kwargs['fileId'] == file_id_to_move
    assert called_kwargs['addParents'] == new_parent_id
    assert called_kwargs['removeParents'] == old_parent_id
    assert called_kwargs['fields'] == 'id, parents'
    mock_google.as_service_account.assert_called_once_with(mock_drive_v3_api.files.update.return_value)

@pytest.mark.asyncio
async def test_move_file_api_call_exception(valid_service: GoogleDriveService, mock_aiogoogle_service_account):
    """
    測試 move_file 方法：當 API 呼叫 files.update 拋出異常時，應返回 False。
    """
    mock_google, _ = mock_aiogoogle_service_account
    mock_google.as_service_account.side_effect = Exception("模擬 API 移動檔案錯誤")

    success = await valid_service.move_file("file_id", "new_parent_id", "old_parent_id")
    assert success is False
    mock_google.as_service_account.assert_called_once()

@pytest.mark.asyncio
async def test_move_file_parents_not_updated(valid_service: GoogleDriveService, mock_aiogoogle_service_account):
    """
    測試 move_file 方法：API 呼叫成功但父資料夾列表未按預期更新。
    """
    mock_google, _ = mock_aiogoogle_service_account
    file_id_to_move = "file_to_move_id_no_update"
    new_parent_id = "new_parent_folder_id_no_update"

    # 模擬 API 回應中 'parents' 列表不包含 new_parent_id
    mock_google.as_service_account.return_value = {"id": file_id_to_move, "parents": ["some_other_parent_id"]}

    success = await valid_service.move_file(file_id_to_move, new_parent_id)
    assert success is False
    mock_google.as_service_account.assert_called_once()


# --- delete_file 測試 ---

@pytest.mark.asyncio
async def test_delete_file_success(valid_service: GoogleDriveService, mock_aiogoogle_service_account):
    """
    測試 delete_file 方法：成功刪除檔案/資料夾。
    """
    mock_google, mock_drive_v3_api = mock_aiogoogle_service_account
    file_id_to_delete = "file_to_delete_id"

    # delete 通常不返回內容，所以 as_service_account 可以返回 None 或一個空的 mock
    mock_google.as_service_account.return_value = None

    success = await valid_service.delete_file(file_id_to_delete)

    assert success is True
    mock_drive_v3_api.files.delete.assert_called_once_with(fileId=file_id_to_delete)
    mock_google.as_service_account.assert_called_once_with(mock_drive_v3_api.files.delete.return_value)

@pytest.mark.asyncio
async def test_delete_file_api_call_exception(valid_service: GoogleDriveService, mock_aiogoogle_service_account):
    """
    測試 delete_file 方法：當 API 呼叫 files.delete 拋出異常時，應返回 False。
    """
    mock_google, _ = mock_aiogoogle_service_account
    mock_google.as_service_account.side_effect = Exception("模擬 API 刪除錯誤")

    success = await valid_service.delete_file("file_id_to_delete_exception")
    assert success is False
    mock_google.as_service_account.assert_called_once()
