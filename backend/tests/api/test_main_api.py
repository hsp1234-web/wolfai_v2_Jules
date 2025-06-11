# -*- coding: utf-8 -*-
import pytest
from fastapi.testclient import TestClient
import os
from pydantic import SecretStr
from unittest.mock import MagicMock

from backend.main import app, app_state
from backend.config import settings, Settings # Import Settings for re-initialization if needed for some tests

# Fixture for the TestClient
@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def test_health_check(client: TestClient):
    response = client.get("/api/v1/health")
    assert response.status_code == 200, f"健康檢查應返回 200 OK，實際: {response.status_code}, {response.text}"
    data = response.json()
    assert "status" in data
    assert "message" in data
    assert "gemini_status" in data
    assert data["status"] in ["正常", "警告", "錯誤"]

def test_verbose_health_check(client: TestClient):
    response = client.get("/api/v1/health/verbose")
    assert response.status_code == 200, f"詳細健康檢查應返回 200 OK，實際: {response.status_code}, {response.text}"
    data = response.json()
    assert "overall_status" in data
    assert "timestamp" in data
    expected_components = [
        "database_status", "gemini_api_status", "google_drive_status",
        "scheduler_status", "filesystem_status", "frontend_service_status"
    ]
    for component in expected_components:
        assert component in data
        assert "status" in data[component]
    assert data["overall_status"] in ["全部正常", "部分異常", "嚴重故障"]

def test_health_check_returns_200_and_basic_status(client: TestClient):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "message" in data
    assert "scheduler_status" in data
    assert "drive_service_status" in data
    assert "config_status" in data
    assert "mode" in data
    assert "gemini_status" in data
    assert isinstance(data["status"], str)
    assert isinstance(data["message"], str)
    assert isinstance(data["mode"], str)
    assert data["mode"] != ""
    assert data["status"] in ["正常", "警告", "錯誤"]

def test_get_api_key_status_default(client: TestClient, mocker):
    mock_gemini_service = mocker.MagicMock()
    mock_gemini_service.is_configured = False

    original_app_state = app_state.copy()
    app_state.update({
        "gemini_service": mock_gemini_service,
        "google_api_key": None,
        "google_api_key_source": None,
        "service_account_info": None
    })
    try:
        response = client.get("/api/v1/get_api_key_status")
        assert response.status_code == 200
        data = response.json()
        assert data.get("GOOGLE_API_KEY") == "未設定"
        assert data.get("legacy_gemini_api_key_is_set") is False
        assert data.get("legacy_gemini_api_key_source") is None
        assert data.get("gemini_service_configured") is False
        assert data.get("drive_service_account_loaded") is False
    finally:
        app_state.clear()
        app_state.update(original_app_state)

def test_get_api_key_status_after_successful_set(client: TestClient, mocker):
    mocker.patch('google.generativeai.configure')

    original_app_state = app_state.copy()
    original_settings_google_api_key = settings.GOOGLE_API_KEY
    original_environ_google_api_key = os.environ.get("GOOGLE_API_KEY")


    # Ensure a mock gemini_service is in app_state for the test to manipulate
    initial_gemini_service_mock = mocker.MagicMock()
    initial_gemini_service_mock.is_configured = False
    app_state["gemini_service"] = initial_gemini_service_mock
    app_state["google_api_key"] = None
    app_state["google_api_key_source"] = None
    app_state["service_account_info"] = True

    try:
        set_key_payload = {"api_key": "a_valid_test_key_for_status_check"}
        set_response = client.post("/api/v1/set_api_key", json=set_key_payload)
        assert set_response.status_code == 200

        status_response = client.get("/api/v1/get_api_key_status")
        assert status_response.status_code == 200
        data = status_response.json()

        assert data.get("GOOGLE_API_KEY") == "已設定"
        assert data.get("legacy_gemini_api_key_is_set") is True
        assert data.get("legacy_gemini_api_key_source") == "user_input"
        assert data.get("gemini_service_configured") is True
        assert data.get("drive_service_account_loaded") is True
    finally:
        app_state.clear()
        app_state.update(original_app_state)

        if original_environ_google_api_key is None:
            if "GOOGLE_API_KEY" in os.environ: del os.environ["GOOGLE_API_KEY"]
        else:
            os.environ["GOOGLE_API_KEY"] = original_environ_google_api_key
        settings.GOOGLE_API_KEY = original_settings_google_api_key


@pytest.mark.parametrize("api_key_value, expected_status_code, expect_gemini_configured_after_set", [
    ("test_valid_key", 200, True),
    ("", 400, False),
    ("   ", 400, False)
])
def test_set_api_key(client: TestClient, mocker, api_key_value: str, expected_status_code: int, expect_gemini_configured_after_set: bool):
    mock_genai_configure = mocker.patch('google.generativeai.configure')

    original_app_state = app_state.copy()
    original_settings_google_api_key = settings.GOOGLE_API_KEY
    original_environ_google_api_key = os.environ.get("GOOGLE_API_KEY")

    mock_gemini_service = MagicMock()
    mock_gemini_service.is_configured = False
    app_state['gemini_service'] = mock_gemini_service

    try:
        if expected_status_code == 400:
            mock_genai_configure.side_effect = Exception("此情況下不應調用 configure")

        response = client.post("/api/v1/set_api_key", json={"api_key": api_key_value})

        assert response.status_code == expected_status_code, \
            f"設定 API 金鑰 '{api_key_value}' 時，預期狀態碼 {expected_status_code}，得到 {response.status_code}。回應: {response.text}"

        if expected_status_code == 200:
            data = response.json()
            assert data["is_set"] is True
            assert data["gemini_configured"] == expect_gemini_configured_after_set
            if api_key_value:
                 mock_genai_configure.assert_called_with(api_key=api_key_value)
        elif expected_status_code == 400:
            data = response.json()
            assert "detail" in data
            assert "API 金鑰不得為空" in data["detail"]
            mock_genai_configure.assert_not_called()
    finally:
        app_state.clear()
        app_state.update(original_app_state)
        if original_environ_google_api_key is None:
            if "GOOGLE_API_KEY" in os.environ: del os.environ["GOOGLE_API_KEY"]
        else:
            os.environ["GOOGLE_API_KEY"] = original_environ_google_api_key
        settings.GOOGLE_API_KEY = original_settings_google_api_key


def test_openapi_json_accessible(client: TestClient):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Wolf AI V2.2 Backend"

ALL_MANAGED_API_KEYS = [
    "GOOGLE_API_KEY", "API_KEY_FRED", "API_KEY_FINMIND",
    "API_KEY_FINNHUB", "API_KEY_FMP", "ALPHA_VANTAGE_API_KEY",
    "DEEPSEEK_API_KEY"
]

def test_get_key_status_all_unset(client: TestClient, mocker):
    for key_name in ALL_MANAGED_API_KEYS:
        mocker.patch.object(settings, key_name, None)

    mock_gemini_service = mocker.MagicMock()
    mock_gemini_service.is_configured = False

    original_app_state = app_state.copy()
    app_state.update({
        "service_account_info": None,
        "gemini_service": mock_gemini_service,
        "google_api_key": None,
        "google_api_key_source": None
    })
    try:
        response = client.get("/api/v1/get_key_status")
        assert response.status_code == 200
        data = response.json()
        for key_name in ALL_MANAGED_API_KEYS:
            assert data.get(key_name) == "未設定", f"金鑰 {key_name} 應為 '未設定'"
        assert data.get("legacy_gemini_api_key_is_set") is False
        assert data.get("legacy_gemini_api_key_source") is None
        assert data.get("drive_service_account_loaded") is False
        assert data.get("gemini_service_configured") is False
    finally:
        app_state.clear()
        app_state.update(original_app_state)

def test_get_key_status_some_set(client: TestClient, mocker):
    mocker.patch.object(settings, "GOOGLE_API_KEY", SecretStr("test_google_key"))
    mocker.patch.object(settings, "API_KEY_FRED", SecretStr("test_fred_key"))
    mocker.patch.object(settings, "API_KEY_FINNHUB", None)
    for key_name in ALL_MANAGED_API_KEYS:
        if key_name not in ["GOOGLE_API_KEY", "API_KEY_FRED", "API_KEY_FINNHUB"]:
            mocker.patch.object(settings, key_name, None)

    mock_gemini_service = mocker.MagicMock()
    mock_gemini_service.is_configured = True

    original_app_state = app_state.copy()
    app_state.update({
        "service_account_info": {"client_email": "test@example.com"},
        "gemini_service": mock_gemini_service,
        "google_api_key": "test_google_key",
        "google_api_key_source": "environment/config"
    })
    try:
        response = client.get("/api/v1/get_key_status")
        assert response.status_code == 200
        data = response.json()
        assert data.get("GOOGLE_API_KEY") == "已設定"
        assert data.get("API_KEY_FRED") == "已設定"
        assert data.get("API_KEY_FINNHUB") == "未設定"
        assert data.get("API_KEY_FINMIND") == "未設定"
        assert data.get("legacy_gemini_api_key_is_set") is True
        assert data.get("legacy_gemini_api_key_source") == "environment/config"
        assert data.get("drive_service_account_loaded") is True
        assert data.get("gemini_service_configured") is True
    finally:
        app_state.clear()
        app_state.update(original_app_state)

def test_set_keys_set_single_key_valid(client: TestClient, mocker):
    key_to_test = "API_KEY_FRED"
    test_value = "fred_test_value_set_keys"
    payload = {key_to_test: test_value}

    original_setting_value = getattr(settings, key_to_test, None)
    original_environ_value = os.environ.get(key_to_test)

    mocker.patch.object(settings, key_to_test, None)
    if key_to_test in os.environ: del os.environ[key_to_test]

    try:
        response = client.post("/api/v1/set_keys", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == f"API 金鑰已處理。受影響的金鑰: {key_to_test}"
        assert key_to_test in data["updated_keys"]
        assert os.environ.get(key_to_test) == test_value
        assert settings.API_KEY_FRED is not None
        assert settings.API_KEY_FRED.get_secret_value() == test_value
    finally:
        if original_environ_value is None:
            if key_to_test in os.environ: del os.environ[key_to_test]
        else:
            os.environ[key_to_test] = original_environ_value
        setattr(settings, key_to_test, original_setting_value)


def test_set_keys_set_google_api_key_reconfigures_gemini(client: TestClient, mocker):
    test_value = "new_google_key_for_gemini_reconfig"
    payload = {"GOOGLE_API_KEY": test_value}
    mock_genai_configure = mocker.patch('backend.main.genai.configure')

    original_app_state = app_state.copy()
    mock_gemini_service_instance = mocker.MagicMock()
    mock_gemini_service_instance.is_configured = False
    app_state["gemini_service"] = mock_gemini_service_instance

    original_settings_google_api_key = settings.GOOGLE_API_KEY
    mocker.patch.object(settings, "GOOGLE_API_KEY", None)

    original_environ_google_api_key = os.environ.get("GOOGLE_API_KEY")
    if "GOOGLE_API_KEY" in os.environ: del os.environ["GOOGLE_API_KEY"]

    try:
        response = client.post("/api/v1/set_keys", json=payload)
        assert response.status_code == 200
        mock_genai_configure.assert_called_once_with(api_key=test_value)
        assert mock_gemini_service_instance.is_configured is True
        assert settings.GOOGLE_API_KEY is not None
        assert settings.GOOGLE_API_KEY.get_secret_value() == test_value
        assert app_state.get("google_api_key") == test_value
        assert app_state.get("google_api_key_source") == "user_input (set_keys)"
    finally:
        app_state.clear()
        app_state.update(original_app_state)
        if original_environ_google_api_key is None:
            if "GOOGLE_API_KEY" in os.environ: del os.environ["GOOGLE_API_KEY"]
        else:
            os.environ["GOOGLE_API_KEY"] = original_environ_google_api_key
        settings.GOOGLE_API_KEY = original_settings_google_api_key


def test_set_keys_clear_single_key_with_empty_string(client: TestClient, mocker):
    key_to_clear = "API_KEY_FMP"
    original_setting_value = settings.API_KEY_FMP
    original_environ_value = os.environ.get(key_to_clear)

    mocker.patch.object(settings, key_to_clear, SecretStr("initial_fmp_value"))
    os.environ[key_to_clear] = "initial_fmp_value"
    try:
        payload = {key_to_clear: ""}
        response = client.post("/api/v1/set_keys", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert key_to_clear in data["updated_keys"]
        assert os.environ.get(key_to_clear) == ""
        assert getattr(settings, key_to_clear) is None
    finally:
        if original_environ_value is None:
            if key_to_clear in os.environ: del os.environ[key_to_clear]
        else:
            os.environ[key_to_clear] = original_environ_value
        setattr(settings, key_to_clear, original_setting_value)


def test_set_keys_clear_single_key_with_none(client: TestClient, mocker):
    key_to_clear = "DEEPSEEK_API_KEY"
    original_setting_value = settings.DEEPSEEK_API_KEY
    original_environ_value = os.environ.get(key_to_clear)

    mocker.patch.object(settings, key_to_clear, SecretStr("initial_deepseek_value"))
    os.environ[key_to_clear] = "initial_deepseek_value"
    try:
        payload = {key_to_clear: None}
        response = client.post("/api/v1/set_keys", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert key_to_clear in data["updated_keys"]
        assert key_to_clear not in os.environ
        assert getattr(settings, key_to_clear) is None
    finally:
        if original_environ_value is None:
            if key_to_clear in os.environ: del os.environ[key_to_clear]
        else:
            os.environ[key_to_clear] = original_environ_value
        setattr(settings, key_to_clear, original_setting_value)


def test_set_keys_multiple_keys(client: TestClient, mocker):
    payload = {
        "API_KEY_FINMIND": "finmind_test_val_multi",
        "API_KEY_FINNHUB": "finnhub_test_val_multi",
        "ALPHA_VANTAGE_API_KEY": ""
    }

    original_environ = os.environ.copy()

    # Store original settings values
    original_finmind = settings.API_KEY_FINMIND
    original_finnhub = settings.API_KEY_FINNHUB
    original_alpha = settings.ALPHA_VANTAGE_API_KEY

    mocker.patch.object(settings, "API_KEY_FINMIND", None)
    mocker.patch.object(settings, "API_KEY_FINNHUB", None)
    mocker.patch.object(settings, "ALPHA_VANTAGE_API_KEY", SecretStr("initial_alpha_value"))

    os.environ.clear()
    os.environ["ALPHA_VANTAGE_API_KEY"] = "initial_alpha_value"

    try:
        response = client.post("/api/v1/set_keys", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "API_KEY_FINMIND" in data["updated_keys"]
        assert "API_KEY_FINNHUB" in data["updated_keys"]
        assert "ALPHA_VANTAGE_API_KEY" in data["updated_keys"]
        assert os.environ.get("API_KEY_FINMIND") == "finmind_test_val_multi"
        assert settings.API_KEY_FINMIND.get_secret_value() == "finmind_test_val_multi"
        assert os.environ.get("API_KEY_FINNHUB") == "finnhub_test_val_multi"
        assert settings.API_KEY_FINNHUB.get_secret_value() == "finnhub_test_val_multi"
        assert os.environ.get("ALPHA_VANTAGE_API_KEY") == ""
        assert settings.ALPHA_VANTAGE_API_KEY is None
    finally:
        os.environ.clear()
        os.environ.update(original_environ)
        # Restore original settings values
        settings.API_KEY_FINMIND = original_finmind
        settings.API_KEY_FINNHUB = original_finnhub
        settings.ALPHA_VANTAGE_API_KEY = original_alpha


def test_set_keys_invalid_key_name_ignored(client: TestClient, mocker):
    valid_key = "API_KEY_FRED"
    valid_value = "fred_value_for_invalid_test"
    payload = {
        "INVALID_KEY_NAME_XYZ": "some_random_value",
        valid_key: valid_value,
        "ANOTHER_BAD_KEY": None
    }

    original_setting_value = getattr(settings, valid_key, None)
    original_environ_value = os.environ.get(valid_key)

    mocker.patch.object(settings, valid_key, None)
    if valid_key in os.environ: del os.environ[valid_key]

    try:
        response = client.post("/api/v1/set_keys", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert valid_key in data["updated_keys"]
        assert "INVALID_KEY_NAME_XYZ" not in data["updated_keys"]
        assert "ANOTHER_BAD_KEY" not in data["updated_keys"]
        assert len(data["updated_keys"]) == 1
        assert os.environ.get(valid_key) == valid_value
        assert settings.API_KEY_FRED.get_secret_value() == valid_value
        assert "INVALID_KEY_NAME_XYZ" not in os.environ
        assert not hasattr(settings, "INVALID_KEY_NAME_XYZ")
    finally:
        if original_environ_value is None:
            if valid_key in os.environ: del os.environ[valid_key]
        else:
            os.environ[valid_key] = original_environ_value
        setattr(settings, valid_key, original_setting_value)


def test_set_keys_no_valid_keys_provided(client: TestClient, mocker):
    payload = {
        "INVALID_KEY_1": "value1",
        "NON_EXISTENT_KEY_2": "value2"
    }
    response = client.post("/api/v1/set_keys", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "未提供任何有效金鑰進行更新。請確保金鑰名稱正確且在允許的列表中。"
    assert len(data["updated_keys"]) == 0
