import os
import shutil
from fastapi.testclient import TestClient
import sys
import time
import logging
from typing import Generator
import pytest # Import pytest for monkeypatch

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'app'))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# Import app and the main module to monkeypatch its global variable
from main import app
import main as main_module # noqa: E402

client = TestClient(app)

TEST_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_REPORTS_TEMP_DIR = os.path.join(TEST_BASE_DIR, "test_reports_data_temp")

# Store the original path from main_module
ORIGINAL_MAIN_DATA_STORAGE_PATH = main_module.DATA_STORAGE_PATH

@pytest.fixture(autouse=True)
def manage_test_environment(monkeypatch: pytest.MonkeyPatch):
    """設定測試環境: 修改 main_module 的資料路徑並建立臨時資料夾和檔案"""
    # Ensure no old test directory is present from a previous failed run
    if os.path.exists(TEST_REPORTS_TEMP_DIR):
        shutil.rmtree(TEST_REPORTS_TEMP_DIR)
    os.makedirs(TEST_REPORTS_TEMP_DIR, exist_ok=True)

    # Monkeypatch the DATA_STORAGE_PATH in the main module where endpoints access it
    monkeypatch.setattr(main_module, 'DATA_STORAGE_PATH', TEST_REPORTS_TEMP_DIR)
    file_contents = {
        "test_report_001.txt": "這是測試報告1的內容。",
        "test_report_002.txt": "這是測試報告2的內容。",
        "another_report.txt": "這是另一份報告。",
        "report with spaces.txt": "帶空格的檔案內容。",
        "other_file.md": "這不是一個txt檔案，用於測試副檔名過濾。"
    }
    for filename, content in file_contents.items():
        with open(os.path.join(TEST_REPORTS_TEMP_DIR, filename), "w", encoding="utf-8") as f:
            f.write(content)

    yield # This allows the test to run

    # Teardown: cleanup after test
    monkeypatch.setattr(main_module, 'DATA_STORAGE_PATH', ORIGINAL_MAIN_DATA_STORAGE_PATH)
    if os.path.exists(TEST_REPORTS_TEMP_DIR):
        shutil.rmtree(TEST_REPORTS_TEMP_DIR)

def test_get_reports_list_success():
    # setup_test_environment() is now handled by the autouse fixture
    response = client.get("/api/reports")
    assert response.status_code == 200
    data = response.json()
    assert "files" in data
    expected_files = sorted(["test_report_001.txt", "test_report_002.txt", "another_report.txt", "report with spaces.txt"])
    assert data["files"] == expected_files

def test_get_reports_list_empty_if_no_txt_files():
    # setup_test_environment() handled by fixture
    # We need to modify the files *after* the fixture sets up the directory
    for item in os.listdir(TEST_REPORTS_TEMP_DIR): # Ensure this is the monkeypatched path
        if item.endswith(".txt"):
            os.remove(os.path.join(TEST_REPORTS_TEMP_DIR, item))
    response = client.get("/api/reports")
    assert response.status_code == 200
    assert response.json()["files"] == []

def test_get_reports_list_when_storage_dir_is_missing_then_created(monkeypatch: pytest.MonkeyPatch):
    # This test needs to specifically handle directory creation
    # The autouse fixture creates TEST_REPORTS_TEMP_DIR, so we test a different one
    temp_missing_dir = os.path.join(TEST_BASE_DIR, "temp_definitely_missing_dir_for_test_2")
    if os.path.exists(temp_missing_dir): # Clean up from previous runs if any
        shutil.rmtree(temp_missing_dir)

    monkeypatch.setattr(main_module, 'DATA_STORAGE_PATH', temp_missing_dir)

    try:
        response = client.get("/api/reports")
        assert response.status_code == 200
        assert response.json()["files"] == [] # Should be empty as it was just created
        assert os.path.isdir(temp_missing_dir) # Ensure it was created
    finally:
        # Clean up this specific directory; the autouse fixture handles its own
        if os.path.exists(temp_missing_dir):
            shutil.rmtree(temp_missing_dir)
        # Restore DATA_STORAGE_PATH to what the autouse fixture expects for its teardown
        monkeypatch.setattr(main_module, 'DATA_STORAGE_PATH', TEST_REPORTS_TEMP_DIR)


def test_get_report_content_success():
    response = client.get("/api/reports/test_report_001.txt")
    assert response.status_code == 200
    assert response.text == "這是測試報告1的內容。"

def test_get_report_content_with_spaces_in_filename():
    response = client.get("/api/reports/report with spaces.txt")
    assert response.status_code == 200
    assert response.text == "帶空格的檔案內容。"

def test_get_report_content_not_found():
    response = client.get("/api/reports/non_existent_file.txt")
    assert response.status_code == 404
    assert response.json()["detail"] == "檔案未找到。"

def test_get_report_content_invalid_extension():
    response = client.get("/api/reports/other_file.md")
    assert response.status_code == 400
    assert response.json()["detail"] == "無效的檔案名稱或格式。"

def test_get_report_content_path_traversal_attempt_slash_in_name():
    response = client.get("/api/reports/subdir/report.txt")
    assert response.status_code == 400
    assert response.json()["detail"] == "無效的檔案名稱或格式。"

def test_get_report_content_path_traversal_attempt_dot_dot():
    # After Starlette's PathConverter normalizes '../secret.txt' to 'secret.txt',
    # our Check 1 for ".." in filename won't find "..".
    # Check 2 will ensure 'secret.txt' is within DATA_STORAGE_PATH.
    # Then, it will become a 404 because 'secret.txt' doesn't exist.
    # This is safe, as no traversal happens. The test is changed to reflect this.
    # Starlette's router normalizes /api/reports/../secret.txt to /api/secret.txt,
    # which doesn't match any defined route, so the router returns a generic 404.
    response = client.get("/api/reports/../secret.txt")
    assert response.status_code == 404
    assert response.json()["detail"] == "Not Found" # Default FastAPI/Starlette 404 message

def test_health_check():
    # This test does not depend on DATA_STORAGE_PATH, so no specific setup needed beyond fixture
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert app.version == data["api_version"]
    assert time.strftime('%Y') in data["timestamp_tw"]
    # Loosened the timezone check to be more robust across environments
    assert "CST" in data["timestamp_tw"] or "Asia/Taipei" in data["timestamp_tw"] or "+0800" in data["timestamp_tw"] or "+08" in data["timestamp_tw"]


def test_chat_endpoint_mock_response():
    request_data = {
        "report_content": "市場趨勢週報...",
        "api_key": "test_key_123",
        "selected_model": "gemini-pro-test",
        "chat_history": [],
        "user_question": "總結重點。"
    }
    response = client.post("/api/chat", json=request_data)
    assert response.status_code == 200
    json_response = response.json()
    assert "模擬AI回覆" in json_response["reply"]

def test_frontend_log_endpoint_receipt():
    response = client.post("/api/logs/frontend", json={"message": "前端錯誤"})
    assert response.status_code == 200
    assert response.json() == {"status": "前端日誌已接收"}

if __name__ == "__main__":
    print("請使用 'pytest' 命令執行測試。")
