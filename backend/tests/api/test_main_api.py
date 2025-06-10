# -*- coding: utf-8 -*-
import pytest
from fastapi.testclient import TestClient
import os

# To test the main app, we need to ensure that settings are loaded correctly,
# or we can override dependencies for testing specific configurations.
# For now, we assume that the default settings (e.g., from environment or .env) are sufficient
# for basic tests, or that services are robust enough to handle missing optional configs.

# Adjust the import path based on your project structure and how you run pytest.
# If running pytest from the 'backend' directory, 'from backend.main import app' might work if 'backend' is in PYTHONPATH.
# If 'backend' is the top-level directory in PYTHONPATH (as set in pytest.ini), then it's 'from main import app'.
# Let's assume pytest.ini's `pythonpath = .` (when run from `backend/` directory) makes `main` importable.
from backend.main import app, app_state # Import FastAPI app instance and app_state for potential mocking/checking
from backend.config import settings # To potentially override or check settings if needed

# Fixture for the TestClient
@pytest.fixture(scope="module") # module scope if app setup is expensive
def client():
    """
    提供一個 FastAPI TestClient 實例。
    """
    # We might need to ensure a clean app_state for each test or module if tests modify it.
    # For now, assuming lifespan events in the app handle setup and app_state is fresh enough.
    # If using a test database, this is where you'd configure it.
    # Example: override settings for DB paths before creating TestClient
    # original_reports_db = settings.REPORTS_DB_PATH
    # settings.REPORTS_DB_PATH = ":memory:"
    # client = TestClient(app)
    # settings.REPORTS_DB_PATH = original_reports_db # Reset
    # yield client

    # For now, use the app as is, assuming lifespan populates app_state correctly for tests.
    # If tests require specific states of app_state services, they might need to mock them.
    with TestClient(app) as c:
        yield c


def test_health_check(client: TestClient):
    """
    測試 /api/health 端點是否返回 200 OK 且包含預期欄位。
    """
    response = client.get("/api/health")
    assert response.status_code == 200, f"健康檢查應返回 200 OK，實際: {response.status_code}, {response.text}"
    data = response.json()
    assert "status" in data, "回應中應包含 'status' 欄位。"
    assert "message" in data, "回應中應包含 'message' 欄位。"
    assert "gemini_status" in data, "回應中應包含 'gemini_status' 欄位。"
    # Basic check, more detailed checks depend on actual app state during test run
    assert data["status"] in ["正常", "警告", "錯誤"], "狀態值應為預期之一。"


def test_verbose_health_check(client: TestClient):
    """
    測試 /api/health/verbose 端點是否返回 200 OK 且包含預期結構。
    """
    response = client.get("/api/health/verbose")
    assert response.status_code == 200, f"詳細健康檢查應返回 200 OK，實際: {response.status_code}, {response.text}"
    data = response.json()

    assert "overall_status" in data, "詳細健康檢查應包含 'overall_status'。"
    assert "timestamp" in data, "詳細健康檢查應包含 'timestamp'。"
    expected_components = [
        "database_status", "gemini_api_status", "google_drive_status",
        "scheduler_status", "filesystem_status", "frontend_service_status"
    ]
    for component in expected_components:
        assert component in data, f"詳細健康檢查應包含 '{component}' 組件狀態。"
        assert "status" in data[component], f"'{component}' 中應有 'status' 欄位。"

    assert data["overall_status"] in ["全部正常", "部分異常", "嚴重故障"], "總體狀態值應為預期之一。"

def test_get_api_key_status_default(client: TestClient, mocker):
    """
    測試 /api/get_api_key_status 端點的預設回應 (假設 Gemini 未配置)。
    """
    # We might need to ensure GeminiService is truly in a non-configured state for this test.
    # This can be tricky if another test configures it globally via genai.configure.
    # For a true unit test of this endpoint, mocking app_state["gemini_service"] might be needed.

    # 確保 app_state 處於預期的初始狀態
    # 模擬 GeminiService 未配置，且沒有 API 金鑰和服務帳號信息
    mock_gemini_service = mocker.MagicMock()
    mock_gemini_service.is_configured = False

    # 使用 mocker.patch.dict 來臨時修改 app_state，測試結束後會自動恢復
    with mocker.patch.dict(app_state, {
        "gemini_service": mock_gemini_service,
        "google_api_key": None,
        "google_api_key_source": None,
        "service_account_info": None
    }):
        response = client.get("/api/get_api_key_status")
        assert response.status_code == 200
        data = response.json()
        assert data["is_set"] is False, "預期 API 金鑰在初始狀態下未設定。"
        assert data["source"] is None, "預期 API 金鑰來源在初始狀態下為 None。"
        assert data["gemini_configured"] is False, "預期 Gemini 在初始狀態下未配置。"
        assert data["drive_service_account_loaded"] is False, "預期 Drive 服務帳號在初始狀態下未載入。"

def test_get_api_key_status_after_successful_set(client: TestClient, mocker):
    """
    測試在成功設定 API 金鑰後，調用 /api/get_api_key_status 是否返回正確的狀態。
    """
    # 模擬 genai.configure 成功執行
    mocker.patch('google.generativeai.configure')

    # 確保 app_state 中的 GeminiService 實例存在且可被修改
    # 通常 lifespan 中會初始化，若無則 mock 一個
    if app_state.get("gemini_service") is None:
        app_state["gemini_service"] = mocker.MagicMock()

    # 初始時，gemini_service 可能已根據環境變數配置，這裡我們先將其重置為未配置狀態
    # 以便清晰地測試 set_api_key 的效果。
    # 注意：如果依賴 lifespan 中的真實 GeminiService 初始化，這種 mock 可能需要更小心處理。
    # 為了測試的獨立性，這裡假設我們可以控制 is_configured 的初始狀態。
    initial_gemini_service_mock = mocker.MagicMock()
    initial_gemini_service_mock.is_configured = False

    with mocker.patch.dict(app_state, {
        "gemini_service": initial_gemini_service_mock,
        "google_api_key": None, # 確保初始沒有 key
        "google_api_key_source": None,
        "service_account_info": True # 假設 SA 金鑰已加載，以隔離測試目標
    }):
        # 步驟 1: 調用 /api/set_api_key 設定一個有效的金鑰
        set_key_payload = {"api_key": "a_valid_test_key_for_status_check"}
        set_response = client.post("/api/set_api_key", json=set_key_payload)
        assert set_response.status_code == 200, f"設定 API 金鑰應成功，得到 {set_response.status_code}, {set_response.text}"

        # set_api_key 端點內部會更新 app_state["gemini_service"].is_configured
        # 我們需要確保 get_api_key_status 反映的是 set_api_key 執行後 app_state 的真實狀態
        # 因此，這裡我們不再 mock gemini_service.is_configured 的最終值，而是依賴 set_api_key 端點的正確執行

        # 步驟 2: 調用 /api/get_api_key_status 獲取狀態
        status_response = client.get("/api/get_api_key_status")
        assert status_response.status_code == 200
        data = status_response.json()

        assert data["is_set"] is True, "成功設定 API 金鑰後，is_set 應為 True。"
        assert data["source"] == "user_input", "API 金鑰來源應為 'user_input'。"
        # 假設 genai.configure 成功後，is_configured 會被設為 True
        assert data["gemini_configured"] is True, "成功設定 API 金鑰且 genai.configure 成功後，gemini_configured 應為 True。"
        assert data["drive_service_account_loaded"] is True, "Drive 服務帳號載入狀態應保持不變 (在此測試中假設為 True)。"


@pytest.mark.parametrize("api_key_value, expected_status_code, expect_gemini_configured_after_set", [
    ("test_valid_key", 200, True),
    ("", 400, False), # Empty key should be a bad request
    ("   ", 400, False) # Whitespace key also bad request
])
def test_set_api_key(client: TestClient, mocker, api_key_value: str, expected_status_code: int, expect_gemini_configured_after_set: bool):
    """
    測試 /api/set_api_key 端點：設定有效和無效的 API 金鑰。
    """
    # Mock the global genai.configure and the GeminiService instance in app_state
    mock_genai_configure_call = mocker.patch('google.generativeai.configure')

    # Ensure GeminiService is present in app_state and can have its 'is_configured' attribute set
    # If GeminiService might not be in app_state (e.g. due to earlier test failure or specific app logic),
    # this test might need to ensure it's there or skip.
    # For this test, we assume GeminiService is initialized and in app_state.
    if "gemini_service" not in app_state or app_state["gemini_service"] is None:
        # If it can be None, create a mock for it for this test
        app_state["gemini_service"] = MagicMock()
        # Default is_configured to False before test, set_api_key endpoint should change it
        app_state["gemini_service"].is_configured = False

    if expected_status_code == 400: # If we expect genai.configure to not be called
        mock_genai_configure_call.side_effect = Exception("此情況下不應調用 configure")

    response = client.post("/api/set_api_key", json={"api_key": api_key_value})

    assert response.status_code == expected_status_code, \
        f"設定 API 金鑰 '{api_key_value}' 時，預期狀態碼 {expected_status_code}，得到 {response.status_code}。回應: {response.text}"

    if expected_status_code == 200:
        data = response.json()
        assert data["is_set"] is True, "成功設定後，is_set 應為 True。"
        assert data["gemini_configured"] == expect_gemini_configured_after_set, \
            f"Gemini 配置狀態預期為 {expect_gemini_configured_after_set}，實際為 {data['gemini_configured']}"
        if api_key_value: # Configure should be called only if key is non-empty and request is not bad
             mock_genai_configure_call.assert_called_with(api_key=api_key_value)
    elif expected_status_code == 400:
        data = response.json()
        assert "detail" in data, "錯誤回應中應包含 'detail'。"
        assert "API 金鑰不得為空" in data["detail"], "錯誤訊息應提示 API 金鑰不得為空。"
        mock_genai_configure_call.assert_not_called()


def test_openapi_json_accessible(client: TestClient):
    """
    測試 OpenAPI JSON (Swagger/OpenAPI schema) 是否可訪問。
    """
    response = client.get("/openapi.json")
    assert response.status_code == 200, "OpenAPI JSON 應可訪問。"
    assert response.json()["info"]["title"] == "Wolf AI V2.2 Backend", "OpenAPI 標題不符。"

# Future tests could include:
# - Tests for endpoints requiring authentication (if any are added).
# - Tests for endpoints that interact with DataAccessLayer, requiring database setup/mocking.
#   For DAL interactions, it's often better to use dependency overrides in FastAPI
#   to inject a DAL instance that uses a test DB or is a mock.
# - Parameterized tests for various valid/invalid inputs to other endpoints.
