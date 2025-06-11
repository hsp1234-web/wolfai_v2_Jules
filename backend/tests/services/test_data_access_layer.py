import pytest
import pytest_asyncio
import aiosqlite
import os
import json
import logging
from unittest import mock
from unittest.mock import AsyncMock # For async methods

from backend.services.data_access_layer import DataAccessLayer

# Test database paths - use in-memory for tests
TEST_REPORTS_DB_PATH = ":memory:"
TEST_PROMPTS_DB_PATH = ":memory:"

@pytest_asyncio.fixture
async def dal_instance():
    """
    Provides a DataAccessLayer instance initialized with in-memory SQLite databases.
    This fixture has function scope, so each test function gets a new DAL instance
    and fresh in-memory databases.
    """
    dal = DataAccessLayer(
        reports_db_path=TEST_REPORTS_DB_PATH,
        prompts_db_path=TEST_PROMPTS_DB_PATH
    )
    # Ensure that the parent directory for DB path is not created for :memory:
    # DAL's _execute_query handles this by checking if db_dir is empty.
    await dal.initialize_databases()
    yield dal
    # Clean up persistent :memory: connections after the test
    await dal.close_connections()


async def test_initialize_databases_creates_tables(dal_instance: DataAccessLayer):
    """
    Tests if initialize_databases correctly creates the necessary tables.
    It verifies this by attempting to insert and retrieve a dummy record,
    which would fail if tables do not exist.
    """
    try:
        # Test reports table
        report_id = await dal_instance.insert_report_data("init_test.txt", "content", "path/init")
        assert report_id is not None
        retrieved_report = await dal_instance.get_report_by_id(report_id)
        assert retrieved_report is not None
        assert retrieved_report["original_filename"] == "init_test.txt"

        # Test prompt_templates table
        prompt_id = await dal_instance.insert_prompt_template("init_test_prompt", "text", "category")
        assert prompt_id is not None
        retrieved_prompt = await dal_instance.get_prompt_template_by_name("init_test_prompt")
        assert retrieved_prompt is not None
        assert retrieved_prompt["name"] == "init_test_prompt"

    except Exception as e:
        pytest.fail(f"Table creation check failed during DAL operation: {e}")

# --- Test Report CRUD Operations ---

async def test_insert_report_data_success(dal_instance: DataAccessLayer):
    filename = "財務報告_2023_Q4.pdf"
    content = "第四季度財務表現強勁，營收同比增長20%。"
    source_path = "/drive/reports/2023/財務報告_2023_Q4.pdf"
    metadata = {"year": 2023, "quarter": "Q4", "公司": "繁體中文公司"}
    status = "待處理"

    report_id = await dal_instance.insert_report_data(filename, content, source_path, metadata, status)
    assert isinstance(report_id, int)
    assert report_id > 0

    retrieved_report = await dal_instance.get_report_by_id(report_id)
    assert retrieved_report is not None
    assert retrieved_report["original_filename"] == filename
    assert retrieved_report["content"] == content
    assert retrieved_report["source_path"] == source_path
    assert json.loads(retrieved_report["metadata"]) == metadata
    assert retrieved_report["status"] == status
    assert "processed_at" in retrieved_report # Should be set by default

async def test_insert_report_data_db_error(dal_instance: DataAccessLayer, mocker):
    mocker.patch.object(dal_instance, '_execute_query', new_callable=AsyncMock, side_effect=aiosqlite.Error("Simulated DB Error"))

    # Patch logging to capture error messages
    mock_logger_error = mocker.patch('logging.Logger.error')

    report_id = await dal_instance.insert_report_data("error_report.txt", "content", "path")

    assert report_id is None
    mock_logger_error.assert_called_once() # Check if logging.error was called

async def test_get_report_by_id_success(dal_instance: DataAccessLayer):
    report_id = await dal_instance.insert_report_data("report1.txt", "content1", "path1")
    assert report_id is not None

    retrieved = await dal_instance.get_report_by_id(report_id)
    assert retrieved is not None
    assert retrieved["id"] == report_id
    assert retrieved["original_filename"] == "report1.txt"

async def test_get_report_by_id_not_found(dal_instance: DataAccessLayer):
    retrieved = await dal_instance.get_report_by_id(99999) # Non-existent ID
    assert retrieved is None

async def test_update_report_status_success(dal_instance: DataAccessLayer):
    report_id = await dal_instance.insert_report_data("report_status.txt", "initial content", "path/status")
    assert report_id is not None

    new_status = "分析完成"
    new_content = "分析後的內容已更新。"
    updated = await dal_instance.update_report_status(report_id, new_status, new_content)
    assert updated is True

    retrieved = await dal_instance.get_report_by_id(report_id)
    assert retrieved is not None
    assert retrieved["status"] == new_status
    assert retrieved["content"] == new_content
    assert "processed_at" in retrieved # Ensure this field is still present
    # We could also check if processed_at timestamp was updated if the logic implies that

async def test_update_report_status_not_found(dal_instance: DataAccessLayer):
    updated = await dal_instance.update_report_status(88888, "新狀態", "新內容")
    assert updated is False

async def test_update_report_analysis_success(dal_instance: DataAccessLayer):
    report_id = await dal_instance.insert_report_data("report_analysis.txt", "content", "path/analysis")
    assert report_id is not None

    analysis = {"summary": "AI分析摘要", "sentiment": "positive"}
    analysis_json = json.dumps(analysis)
    new_status = "已完成分析"

    updated = await dal_instance.update_report_analysis(report_id, analysis_json, new_status)
    assert updated is True

    retrieved = await dal_instance.get_report_by_id(report_id)
    assert retrieved is not None
    assert retrieved["status"] == new_status
    assert json.loads(retrieved["analysis_json"]) == analysis

async def test_update_report_metadata_success(dal_instance: DataAccessLayer):
    initial_metadata = {"project": "Alpha", "version": 1}
    report_id = await dal_instance.insert_report_data("meta_report.txt", "content", "path/meta", metadata=initial_metadata)
    assert report_id is not None

    update_data = {"version": 2, "editor": "測試員"}
    updated = await dal_instance.update_report_metadata(report_id, update_data)
    assert updated is True

    retrieved = await dal_instance.get_report_by_id(report_id)
    assert retrieved is not None
    expected_metadata = {"project": "Alpha", "version": 2, "editor": "測試員"}
    assert json.loads(retrieved["metadata"]) == expected_metadata

async def test_update_report_metadata_no_initial_metadata(dal_instance: DataAccessLayer):
    report_id = await dal_instance.insert_report_data("no_meta_report.txt", "content", "path/no_meta")
    assert report_id is not None

    new_metadata = {"assignee": "張三"}
    updated = await dal_instance.update_report_metadata(report_id, new_metadata)
    assert updated is True

    retrieved = await dal_instance.get_report_by_id(report_id)
    assert retrieved is not None
    assert json.loads(retrieved["metadata"]) == new_metadata

async def test_update_report_metadata_report_not_found(dal_instance: DataAccessLayer):
    updated = await dal_instance.update_report_metadata(77777, {"data": "value"})
    assert updated is False

async def test_check_report_exists_by_source_path(dal_instance: DataAccessLayer):
    source_path_exists = "/unique/reports/report_q1.docx"
    source_path_not_exists = "/unique/reports/report_q2.docx"

    await dal_instance.insert_report_data("report_q1.docx", "content", source_path_exists)

    assert await dal_instance.check_report_exists_by_source_path(source_path_exists) is True
    assert await dal_instance.check_report_exists_by_source_path(source_path_not_exists) is False

# --- Test Prompt Template CRUD Operations ---

async def test_insert_prompt_template_success(dal_instance: DataAccessLayer):
    name = "總結報告提示詞"
    template_text = "請總結以下報告：\n{report_content}\n並提取關鍵點。"
    category = "財務分析"

    template_id = await dal_instance.insert_prompt_template(name, template_text, category)
    assert isinstance(template_id, int)
    assert template_id > 0

    retrieved = await dal_instance.get_prompt_template_by_name(name)
    assert retrieved is not None
    assert retrieved["name"] == name
    assert retrieved["template_text"] == template_text
    assert retrieved["category"] == category
    assert "created_at" in retrieved
    assert "updated_at" in retrieved

async def test_insert_prompt_template_duplicate_name(dal_instance: DataAccessLayer, mocker):
    name = "唯一的提示詞"
    await dal_instance.insert_prompt_template(name, "text1", "cat1")

    # Patch logging to capture error messages
    mock_logger_error = mocker.patch('logging.Logger.error')

    template_id_duplicate = await dal_instance.insert_prompt_template(name, "text2", "cat2")
    assert template_id_duplicate is None

    # Check that the specific error message from insert_prompt_template was logged
    found_specific_log = False
    expected_log_fragment = f"插入提示詞範本 '{name}' 失敗" # The error 'e' part can vary (UNIQUE constraint failed...)
    for call_args in mock_logger_error.call_args_list:
        logged_message = call_args[0][0] # First argument of the call
        if expected_log_fragment in logged_message:
            found_specific_log = True
            break
    assert found_specific_log, f"Expected log containing '{expected_log_fragment}' not found."

async def test_get_prompt_template_by_name_success(dal_instance: DataAccessLayer):
    name = "查詢測試提示詞"
    await dal_instance.insert_prompt_template(name, "text", "cat")

    retrieved = await dal_instance.get_prompt_template_by_name(name)
    assert retrieved is not None
    assert retrieved["name"] == name

async def test_get_prompt_template_by_name_not_found(dal_instance: DataAccessLayer):
    retrieved = await dal_instance.get_prompt_template_by_name("不存在的提示詞")
    assert retrieved is None

async def test_get_all_prompt_templates_success_and_pagination(dal_instance: DataAccessLayer):
    await dal_instance.insert_prompt_template("T1", "text", "A")
    await dal_instance.insert_prompt_template("T2", "text", "B")
    await dal_instance.insert_prompt_template("T3", "text", "A")

    # Get all
    all_templates = await dal_instance.get_all_prompt_templates(limit=10, offset=0)
    assert len(all_templates) == 3
    # Default order is by name ASC
    assert all_templates[0]["name"] == "T1"
    assert all_templates[1]["name"] == "T2"
    assert all_templates[2]["name"] == "T3"

    # Test limit
    limited = await dal_instance.get_all_prompt_templates(limit=1)
    assert len(limited) == 1
    assert limited[0]["name"] == "T1"

    # Test offset
    offset_templates = await dal_instance.get_all_prompt_templates(limit=1, offset=1)
    assert len(offset_templates) == 1
    assert offset_templates[0]["name"] == "T2"

    # Test limit and offset together
    paginated = await dal_instance.get_all_prompt_templates(limit=2, offset=1)
    assert len(paginated) == 2
    assert paginated[0]["name"] == "T2"
    assert paginated[1]["name"] == "T3"


async def test_get_all_prompt_templates_empty(dal_instance: DataAccessLayer):
    templates = await dal_instance.get_all_prompt_templates()
    assert templates == []

# --- Test _execute_query specific logic ---

@mock.patch('os.makedirs')
@mock.patch('os.path.exists')
async def test_execute_query_create_directory(mock_path_exists: mock.MagicMock, mock_makedirs: mock.MagicMock):
    mock_path_exists.return_value = False # Simulate directory does not exist

    # Need a DAL instance with a file-based path to trigger directory creation
    # This test is a bit tricky because the fixture uses :memory:
    # We'll create a temporary DAL instance for this specific test
    temp_db_path = "./test_dbs/temp_reports.db"
    if os.path.exists(temp_db_path): # Clean up if exists from previous failed run
        os.remove(temp_db_path)
    if os.path.exists("./test_dbs"):
        # Ensure ./test_dbs is empty or remove it to avoid interference
        pass


    dal_for_dir_test = DataAccessLayer(reports_db_path=temp_db_path, prompts_db_path=":memory:")

    # initialize_databases will try to create tables, thus calling _execute_query
    try:
        await dal_for_dir_test.initialize_databases()
    except aiosqlite.Error:
        # We expect this to fail if db doesn't exist and can't be created by aiosqlite without the dir
        # But we are interested in os.makedirs call
        pass

    expected_dir = os.path.dirname(temp_db_path) # Should be "./test_dbs"
    mock_path_exists.assert_called_with(expected_dir)
    mock_makedirs.assert_called_with(expected_dir, exist_ok=True)

    # Clean up the dummy db file and dir if created by the test itself
    if os.path.exists(temp_db_path):
        os.remove(temp_db_path)
    if os.path.exists(expected_dir) and not os.listdir(expected_dir): # remove if empty
        os.rmdir(expected_dir)


async def test_execute_query_insert_returns_rowid(dal_instance: DataAccessLayer, mocker):
    # Spy on the _execute_query method
    # Can't directly spy on async method's return value easily without more complex setup
    # Instead, we rely on the success of insert_report_data which should return the rowid

    filename = "rowid_test.pdf"
    content = "Test for rowid return."
    source_path = "/test/rowid_test.pdf"

    # The actual _execute_query is called internally by insert_report_data
    # We verify its behavior through the public method's result
    report_id = await dal_instance.insert_report_data(filename, content, source_path)

    assert isinstance(report_id, int)
    assert report_id > 0 # rowid should be positive if insert was successful

    # To directly test _execute_query's return, we would need to make it public or test it via a method that uses it.
    # Example of direct call if it were public (conceptual):
    # query = "INSERT INTO reports (original_filename, content, source_path) VALUES (?, ?, ?)"
    # params = (filename, content, source_path)
    # row_id = await dal_instance._execute_query(dal_instance.reports_db_path, query, params, commit=True, fetch_one=False, fetch_all=False)
    # assert isinstance(row_id, int)


# Placeholder for logging tests (more advanced)
# @pytest.mark.asyncio
# async def test_db_error_logs_message(dal_instance: DataAccessLayer, mocker):
#     mocker.patch.object(dal_instance, '_execute_query', side_effect=aiosqlite.Error("DB Error"))
#     mock_log_error = mocker.patch('logging.Logger.error')
#     await dal_instance.insert_report_data("test.txt", "content", "path")
#     mock_log_error.assert_called_once()

# Final placeholder test from the original template (if needed, but covered by others)
def test_placeholder(): # This is a sync test, no asyncio marker needed
    assert True
