# -*- coding: utf-8 -*-
import pytest
import asyncio # Required for async tests if not using pytest-asyncio's auto mode
import os
import json
from backend.services.data_access_layer import DataAccessLayer

# Use pytest-asyncio for async tests: mark with @pytest.mark.asyncio
# Ensure pytest.ini has asyncio_mode = auto or tests are marked.

@pytest.fixture
async def dal_in_memory():
    """
    提供一個使用記憶體中 SQLite 資料庫的 DataAccessLayer 實例。
    此 fixture 的作用域為 'function'，因此每個測試函數都會獲得一個新的資料庫。
    """
    # 使用 :memory: 來創建一個記憶體中的 SQLite 資料庫，專用於測試
    # 為報告和提示詞使用不同的記憶體資料庫，或在檔名後加隨機後綴以模擬分離
    # 但對於簡單的DAL測試，共用一個記憶體DB通常也可以，只要表名不衝突
    # 此處DAL設計是分開的DB檔案，所以我們用不同的 in-memory DB 名稱 (SQLite允許這樣)
    # 或者，我們可以傳遞 None 給路徑，讓 DAL 自己處理（如果它支援 :memory:）
    # 根據 DAL 的實現，它可能會在路徑上創建目錄，:memory: 不需要目錄。
    # We need to ensure that the DAL doesn't try to create directories for :memory:
    # A simple way is to patch os.makedirs if DAL's _execute_query tries to create dirs for :memory: paths.
    # However, current DAL's _execute_query checks `if db_dir and not os.path.exists(db_dir):`
    # For ":memory:", db_dir will be empty, so makedirs won't be called.

    reports_db_path = ":memory:"
    prompts_db_path = ":memory:" # Can be the same in-memory db for testing simplicity if tables are distinct
                                 # Or use "file::memory:?cache=shared" with different connection objects if true separation is needed.
                                 # For this DAL, it seems it manages connections per call, so ":memory:" should be fine.

    dal = DataAccessLayer(reports_db_path=reports_db_path, prompts_db_path=prompts_db_path)
    await dal.initialize_databases() # 創建表結構
    return dal

@pytest.mark.asyncio
async def test_initialize_databases(dal_in_memory: DataAccessLayer):
    """
    測試資料庫初始化是否能成功執行。
    實際的表結構檢查比較複雜，這裡我們假設如果 initialize_databases 不拋錯即為基本成功。
    更進階的測試可以查詢 sqlite_master 表。
    """
    # The fixture already calls initialize_databases.
    # This test mainly ensures the fixture setup itself doesn't fail.
    assert dal_in_memory is not None, "DAL 實例未能成功初始化。"
    # A simple check: try to insert and retrieve data to ensure tables are there.
    report_id = await dal_in_memory.insert_report_data("test.txt", "content", "test/path", status="測試中")
    assert report_id is not None
    retrieved = await dal_in_memory.get_report_by_id(report_id)
    assert retrieved is not None
    assert retrieved['original_filename'] == "test.txt"

@pytest.mark.asyncio
async def test_insert_and_get_report(dal_in_memory: DataAccessLayer):
    """
    測試插入報告數據後能否正確查詢到。
    """
    filename = "財務報告_Q1.pdf"
    content = "第一季度財務表現優異。"
    source_path = "/drive/reports/財務報告_Q1.pdf"
    metadata = {"year": 2024, "quarter": 1}

    report_id = await dal_in_memory.insert_report_data(filename, content, source_path, metadata, status="已存檔")
    assert report_id is not None, "插入報告應返回一個 ID。"

    retrieved_report = await dal_in_memory.get_report_by_id(report_id)
    assert retrieved_report is not None, "應能根據 ID 查詢到報告。"
    assert retrieved_report["id"] == report_id
    assert retrieved_report["original_filename"] == filename
    assert retrieved_report["content"] == content
    assert retrieved_report["source_path"] == source_path
    assert retrieved_report["status"] == "已存檔" # Status was passed during insert
    assert json.loads(retrieved_report["metadata"]) == metadata
    assert "analysis_json" in retrieved_report # Check new column exists
    assert retrieved_report["analysis_json"] is None # Should be None initially

@pytest.mark.asyncio
async def test_update_report_status(dal_in_memory: DataAccessLayer):
    """
    測試更新報告狀態。
    """
    report_id = await dal_in_memory.insert_report_data("weekly.txt", "週報內容", "path/to/weekly.txt")
    assert report_id is not None

    new_status = "分析完成"
    update_success = await dal_in_memory.update_report_status(report_id, new_status, "更新後的內容")
    assert update_success, "更新報告狀態應成功。"

    updated_report = await dal_in_memory.get_report_by_id(report_id)
    assert updated_report is not None
    assert updated_report["status"] == new_status
    assert updated_report["content"] == "更新後的內容"

@pytest.mark.asyncio
async def test_update_report_analysis(dal_in_memory: DataAccessLayer):
    """
    測試更新報告的 AI 分析結果和狀態。
    """
    report_id = await dal_in_memory.insert_report_data("monthly.txt", "月報", "path/to/monthly.txt")
    assert report_id is not None

    analysis_data = {"summary": "這是一個摘要", "keywords": ["AI", "報告"]}
    analysis_json = json.dumps(analysis_data, ensure_ascii=False)
    new_status = "分析完成"

    update_success = await dal_in_memory.update_report_analysis(report_id, analysis_json, new_status)
    assert update_success, "更新報告分析結果應成功。"

    updated_report = await dal_in_memory.get_report_by_id(report_id)
    assert updated_report is not None
    assert updated_report["status"] == new_status
    assert json.loads(updated_report["analysis_json"]) == analysis_data

@pytest.mark.asyncio
async def test_get_all_reports(dal_in_memory: DataAccessLayer):
    """
    測試獲取所有報告列表的功能。
    """
    await dal_in_memory.insert_report_data("report1.txt", "c1", "p1")
    await dal_in_memory.insert_report_data("report2.txt", "c2", "p2")

    reports = await dal_in_memory.get_all_reports(limit=10, offset=0)
    assert len(reports) == 2, "應返回正確數量的報告。"
    assert reports[0]["original_filename"] == "report2.txt" # Default order is DESC by processed_at
    assert reports[1]["original_filename"] == "report1.txt"

@pytest.mark.asyncio
async def test_check_report_exists(dal_in_memory: DataAccessLayer):
    """
    測試檢查報告是否已存在的功能。
    """
    source_path = "unique/path/to/report.doc"
    exists_before = await dal_in_memory.check_report_exists_by_source_path(source_path)
    assert not exists_before, "新報告路徑不應存在於資料庫中。"

    await dal_in_memory.insert_report_data("report.doc", "content", source_path)

    exists_after = await dal_in_memory.check_report_exists_by_source_path(source_path)
    assert exists_after, "已插入的報告應能被檢測到存在。"

# Similar tests can be written for prompt_templates table:
# test_insert_and_get_prompt_template, test_get_all_prompt_templates etc.

@pytest.mark.asyncio
async def test_insert_and_get_prompt_template(dal_in_memory: DataAccessLayer):
    """測試提示詞範本的插入和查詢。"""
    name = "測試提示詞"
    text = "這是一個測試用的提示內容：{placeholder}"
    category = "測試"

    template_id = await dal_in_memory.insert_prompt_template(name, text, category)
    assert template_id is not None, "插入提示詞範本應返回 ID。"

    retrieved_template = await dal_in_memory.get_prompt_template_by_name(name)
    assert retrieved_template is not None
    assert retrieved_template["name"] == name
    assert retrieved_template["template_text"] == text
    assert retrieved_template["category"] == category

@pytest.mark.asyncio
async def test_dal_robustness_against_failed_queries(dal_in_memory: DataAccessLayer, mocker):
    """
    測試當資料庫操作失敗時，DAL 是否能適當處理錯誤（例如不崩潰）。
    """
    # 模擬 _execute_query 拋出異常
    mocker.patch.object(dal_in_memory, '_execute_query', side_effect=aiosqlite.Error("模擬資料庫錯誤"))

    # 嘗試插入操作，預期它會失敗並返回 None 或被捕獲
    report_id = await dal_in_memory.insert_report_data("fail.txt", "content", "fail/path")
    assert report_id is None, "在資料庫錯誤時，插入操作應返回 None。"

    # 嘗試查詢操作，預期返回 None 或空列表
    report = await dal_in_memory.get_report_by_id(1)
    assert report is None

    reports = await dal_in_memory.get_all_reports()
    assert reports == []

    # 測試更新操作
    success = await dal_in_memory.update_report_status(1, "新狀態")
    assert not success

    # 測試帶有分析的更新
    analysis_success = await dal_in_memory.update_report_analysis(1, "{}", "分析失敗")
    assert not analysis_success

    # 檢查存在性應返回 False (或不拋錯)
    exists = await dal_in_memory.check_report_exists_by_source_path("any/path")
    assert not exists

    logger.info("已測試 DAL 在模擬資料庫錯誤時的行為。")
