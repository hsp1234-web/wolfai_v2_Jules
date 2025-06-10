# -*- coding: utf-8 -*-
import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch

from backend.services.report_ingestion_service import ReportIngestionService
# 為類型提示導入依賴服務的類別，但我們將在測試中 mock 它們的實例
from backend.services.google_drive_service import GoogleDriveService
from backend.services.data_access_layer import DataAccessLayer
from backend.services.parsing_service import ParsingService
from backend.services.gemini_service import GeminiService


@pytest.fixture
def mock_drive_service_optional() -> MagicMock:
    """
    提供一個 GoogleDriveService 的可選模擬實例 (可以是 None 或 AsyncMock)。
    在某些測試中，我們可能不需要 Drive Service。
    """
    # 預設返回一個 AsyncMock，測試可以根據需要覆蓋它為 None
    return AsyncMock(spec=GoogleDriveService)

@pytest.fixture
def mock_dal() -> AsyncMock:
    """提供一個 DataAccessLayer 的模擬實例。"""
    return AsyncMock(spec=DataAccessLayer)

@pytest.fixture
def mock_parsing_service() -> MagicMock:
    """提供一個 ParsingService 的模擬實例。"""
    # extract_text_from_file 是同步方法
    mock = MagicMock(spec=ParsingService)
    mock.extract_text_from_file.return_value = "這是模擬的已解析報告內容。"
    return mock

@pytest.fixture
def mock_gemini_service() -> AsyncMock:
    """提供一個 GeminiService 的模擬實例。"""
    return AsyncMock(spec=GeminiService)

@pytest.fixture
def report_ingestion_service(
    mock_drive_service_optional: Optional[AsyncMock], # 使用可選的 mock
    mock_dal: AsyncMock,
    mock_parsing_service: MagicMock,
    mock_gemini_service: AsyncMock
) -> ReportIngestionService:
    """
    提供一個 ReportIngestionService 的實例，並已注入所有模擬的依賴服務。
    """
    return ReportIngestionService(
        drive_service=mock_drive_service_optional,
        dal=mock_dal,
        parsing_service=mock_parsing_service,
        gemini_service=mock_gemini_service
    )

# --- __init__ 測試 ---
def test_report_ingestion_service_initialization(
    report_ingestion_service: ReportIngestionService,
    mock_drive_service_optional: Optional[AsyncMock],
    mock_dal: AsyncMock,
    mock_parsing_service: MagicMock,
    mock_gemini_service: AsyncMock
):
    """
    測試 ReportIngestionService 是否能被成功初始化，並且所有依賴服務都被正確賦值。
    """
    assert report_ingestion_service.drive_service is mock_drive_service_optional
    assert report_ingestion_service.dal is mock_dal
    assert report_ingestion_service.parsing_service is mock_parsing_service
    assert report_ingestion_service.gemini_service is mock_gemini_service

# --- _analyze_and_store_report 測試 ---

@pytest.mark.asyncio
async def test_analyze_and_store_report_success(
    report_ingestion_service: ReportIngestionService,
    mock_gemini_service: AsyncMock,
    mock_dal: AsyncMock
):
    """
    測試 _analyze_and_store_report：當 GeminiService 成功返回分析結果，
    且 DataAccessLayer 成功更新時的行為。
    """
    report_db_id = 1
    test_content = "這是一份需要分析的報告內容。"
    test_file_name = "report.txt"
    mock_analysis_result = {"summary": "這是分析摘要", "findings": ["發現1", "發現2"]}

    mock_gemini_service.analyze_report.return_value = mock_analysis_result
    mock_dal.update_report_analysis.return_value = True # 假設更新成功

    await report_ingestion_service._analyze_and_store_report(report_db_id, test_content, test_file_name)

    mock_gemini_service.analyze_report.assert_called_once_with(test_content)
    expected_analysis_json = json.dumps(mock_analysis_result, ensure_ascii=False)
    mock_dal.update_report_analysis.assert_called_once_with(report_db_id, expected_analysis_json, "分析完成")

@pytest.mark.asyncio
async def test_analyze_and_store_report_empty_or_error_content(
    report_ingestion_service: ReportIngestionService,
    mock_gemini_service: AsyncMock,
    mock_dal: AsyncMock
):
    """
    測試 _analyze_and_store_report：當輸入內容為空或為錯誤指示符時，應跳過 AI 分析。
    """
    report_db_id = 2
    file_name = "empty_report.txt"

    # 測試空內容
    await report_ingestion_service._analyze_and_store_report(report_db_id, "", file_name)
    mock_gemini_service.analyze_report.assert_not_called()
    mock_dal.update_report_analysis.assert_not_called()

    # 測試以 "[" 開頭的內容 (通常表示解析服務返回的錯誤訊息)
    await report_ingestion_service._analyze_and_store_report(report_db_id, "[解析錯誤]", file_name)
    mock_gemini_service.analyze_report.assert_not_called() # 仍然不應調用
    mock_dal.update_report_analysis.assert_not_called() # 仍然不應調用

@pytest.mark.asyncio
async def test_analyze_and_store_report_gemini_returns_error(
    report_ingestion_service: ReportIngestionService,
    mock_gemini_service: AsyncMock,
    mock_dal: AsyncMock
):
    """
    測試 _analyze_and_store_report：當 GeminiService 返回包含錯誤訊息的字典時。
    """
    report_db_id = 3
    test_content = "一些內容。"
    test_file_name = "gemini_error_report.txt"
    gemini_error_response = {"錯誤": "Gemini分析時發生特定錯誤"}

    mock_gemini_service.analyze_report.return_value = gemini_error_response

    await report_ingestion_service._analyze_and_store_report(report_db_id, test_content, test_file_name)

    mock_gemini_service.analyze_report.assert_called_once_with(test_content)
    expected_error_json = json.dumps({"錯誤": "Gemini分析時發生特定錯誤", "原始分析結果": gemini_error_response}, ensure_ascii=False)
    mock_dal.update_report_analysis.assert_called_once_with(report_db_id, expected_error_json, "分析失敗")

@pytest.mark.asyncio
async def test_analyze_and_store_report_gemini_returns_none(
    report_ingestion_service: ReportIngestionService,
    mock_gemini_service: AsyncMock,
    mock_dal: AsyncMock
):
    """
    測試 _analyze_and_store_report：當 GeminiService 返回 None (可能表示服務未配置或嚴重錯誤) 時。
    """
    report_db_id = 4
    test_content = "另一些內容。"
    test_file_name = "gemini_none_report.txt"

    mock_gemini_service.analyze_report.return_value = None # 模擬 GeminiService 返回 None

    await report_ingestion_service._analyze_and_store_report(report_db_id, test_content, test_file_name)

    mock_gemini_service.analyze_report.assert_called_once_with(test_content)
    # 根據 _analyze_and_store_report 的邏輯, 如果 analysis_result 為 None，error_message 會是 "未知分析錯誤或服務未配置"
    expected_error_message = "未知分析錯誤或服務未配置"
    expected_error_json = json.dumps({"錯誤": expected_error_message, "原始分析結果": None}, ensure_ascii=False)
    mock_dal.update_report_analysis.assert_called_once_with(report_db_id, expected_error_json, "分析失敗")

@pytest.mark.asyncio
async def test_analyze_and_store_report_gemini_raises_exception(
    report_ingestion_service: ReportIngestionService,
    mock_gemini_service: AsyncMock,
    mock_dal: AsyncMock
):
    """
    測試 _analyze_and_store_report：當 GeminiService.analyze_report 拋出未預期異常時。
    """
    report_db_id = 5
    test_content = "導致異常的內容。"
    test_file_name = "gemini_exception_report.txt"
    simulated_exception = Exception("模擬Gemini服務內部嚴重錯誤")

    mock_gemini_service.analyze_report.side_effect = simulated_exception

    await report_ingestion_service._analyze_and_store_report(report_db_id, test_content, test_file_name)

    mock_gemini_service.analyze_report.assert_called_once_with(test_content)
    expected_error_json = json.dumps({"錯誤": f"分析過程中發生意外: {simulated_exception}"}, ensure_ascii=False)
    mock_dal.update_report_analysis.assert_called_once_with(report_db_id, expected_error_json, "分析失敗(系統異常)")

@pytest.mark.asyncio
async def test_analyze_and_store_report_dal_update_raises_exception(
    report_ingestion_service: ReportIngestionService,
    mock_gemini_service: AsyncMock,
    mock_dal: AsyncMock
):
    """
    測試 _analyze_and_store_report：當 DataAccessLayer.update_report_analysis 拋出異常時。
    這個測試驗證 _analyze_and_store_report 中的 try...except 是否能捕獲 DAL 的錯誤。
    """
    report_db_id = 6
    test_content = "內容。"
    test_file_name = "dal_exception_report.txt"
    mock_analysis_result = {"summary": "分析成功"}
    simulated_dal_exception = Exception("模擬資料庫更新失敗")

    mock_gemini_service.analyze_report.return_value = mock_analysis_result
    # 模擬 DAL 更新時拋出錯誤
    mock_dal.update_report_analysis.side_effect = simulated_dal_exception

    # 由於 _analyze_and_store_report 中的異常處理會捕獲此異常並嘗試再次更新DAL（記錄錯誤），
    # 我們需要確保第二次DAL調用（記錄錯誤的）不會再次觸發我們這裡的side_effect，或者我們只關心第一次調用。
    # 為了簡化，我們只驗證第一次調用，並預期函數不會因DAL錯誤而崩潰。
    # 更好的做法可能是讓 DAL 的 mock 更智能，或者檢查日誌中是否有相應的錯誤記錄。
    # 此處假設 _analyze_and_store_report 捕獲了 DAL 異常並已記錄，不會向外拋出。

    await report_ingestion_service._analyze_and_store_report(report_db_id, test_content, test_file_name)

    mock_gemini_service.analyze_report.assert_called_once_with(test_content)
    expected_analysis_json = json.dumps(mock_analysis_result, ensure_ascii=False)
    # 第一次嘗試更新（成功的分析結果）
    mock_dal.update_report_analysis.assert_any_call(report_db_id, expected_analysis_json, "分析完成")

    # 由於第一次 DAL 更新失敗，會進入 except Exception as e 塊，
    # 然後再次調用 update_report_analysis 來記錄這個 DAL 錯誤本身。
    # 我們需要確保第二次調用確實發生了，並且是記錄了前一個DAL異常。
    # 這裡我們檢查調用次數和第二次調用的參數。
    assert mock_dal.update_report_analysis.call_count == 2
    args_list = mock_dal.update_report_analysis.call_args_list

    # 檢查第二次調用（記錄錯誤）
    # args_list[1] 是第二次調用, args_list[1][0] 是位置參數元組, args_list[1][1] 是關鍵字參數字典
    second_call_args = args_list[1][0] # (report_db_id, error_json_str, status_str)
    assert second_call_args[0] == report_db_id
    assert json.loads(second_call_args[1]) == {"錯誤": f"分析過程中發生意外: {simulated_dal_exception}"}
    assert second_call_args[2] == "分析失敗(系統異常)"


@pytest.fixture
def report_ingestion_service_no_drive(
    mock_dal: AsyncMock,
    mock_parsing_service: MagicMock,
    mock_gemini_service: AsyncMock
) -> ReportIngestionService:
    """
    提供一個 ReportIngestionService 實例，其中 drive_service 為 None。
    """
    return ReportIngestionService(
        drive_service=None, # 明確設置 drive_service 為 None
        dal=mock_dal,
        parsing_service=mock_parsing_service,
        gemini_service=mock_gemini_service
    )

# --- _archive_file_in_drive 測試 ---

@pytest.mark.asyncio
async def test_archive_file_in_drive_success(
    report_ingestion_service: ReportIngestionService,
    mock_drive_service_optional: AsyncMock
):
    """
    測試 _archive_file_in_drive：成功刪除 Drive 中的檔案。
    """
    mock_drive_service_optional.delete_file.return_value = True # 模擬刪除成功
    file_id = "file_to_delete"
    file_name = "old_report.txt"

    result = await report_ingestion_service._archive_file_in_drive(file_id, file_name, "processed_folder", "original_folder")

    assert result == "deleted_from_inbox"
    mock_drive_service_optional.delete_file.assert_called_once_with(file_id)

@pytest.mark.asyncio
async def test_archive_file_in_drive_service_not_initialized(
    report_ingestion_service_no_drive: ReportIngestionService # 使用 drive_service 為 None 的 fixture
):
    """
    測試 _archive_file_in_drive：當 Drive Service 未初始化時。
    """
    result = await report_ingestion_service_no_drive._archive_file_in_drive("file_id", "file_name", "proc_id", "orig_id")
    assert result == "error_drive_service_null"

@pytest.mark.asyncio
async def test_archive_file_in_drive_delete_fails(
    report_ingestion_service: ReportIngestionService,
    mock_drive_service_optional: AsyncMock
):
    """
    測試 _archive_file_in_drive：當 Drive Service 的 delete_file 操作返回 False (操作未成功) 時。
    """
    mock_drive_service_optional.delete_file.return_value = False # 模擬刪除失敗

    result = await report_ingestion_service._archive_file_in_drive("file_id", "file_name", "proc_id", "orig_id")

    assert result == "delete_from_inbox_failed"
    mock_drive_service_optional.delete_file.assert_called_once_with("file_id")

@pytest.mark.asyncio
async def test_archive_file_in_drive_delete_raises_exception(
    report_ingestion_service: ReportIngestionService,
    mock_drive_service_optional: AsyncMock
):
    """
    測試 _archive_file_in_drive：當 Drive Service 的 delete_file 操作拋出異常時。
    """
    mock_drive_service_optional.delete_file.side_effect = Exception("模擬 Drive API 刪除錯誤")

    result = await report_ingestion_service._archive_file_in_drive("file_id", "file_name", "proc_id", "orig_id")

    assert result == "delete_exception"
    mock_drive_service_optional.delete_file.assert_called_once_with("file_id")

@pytest.mark.asyncio
async def test_archive_file_in_drive_delete_method_missing(
    report_ingestion_service: ReportIngestionService,
    mock_drive_service_optional: AsyncMock,
    mocker # 需要 mocker 來修改 mock_drive_service_optional 的行為
):
    """
    測試 _archive_file_in_drive：當 Drive Service 實例沒有 delete_file 方法時 (理論上不應發生，但測試健壯性)。
    """
    # 移除 mock_drive_service_optional 上的 delete_file 方法
    mocker.patch.object(mock_drive_service_optional, 'delete_file', create=False, side_effect=AttributeError)
    # 'create=False' 確保如果屬性不存在，patch 會失敗，但這裡我們是用 side_effect=AttributeError 來模擬方法不存在的效果
    # 或者更直接地： del mock_drive_service_optional.delete_file (如果 mock 允許)
    # 但 side_effect=AttributeError 是更安全的 mock 方式

    # 如果 drive_service 是 MagicMock 或 AsyncMock，可以直接 del
    if hasattr(mock_drive_service_optional, 'delete_file') and isinstance(mock_drive_service_optional, (MagicMock, AsyncMock)):
         del mock_drive_service_optional.delete_file
    else: # 如果是 spec=GoogleDriveService 且 create=True (預設)，則 hasattr 會是 True
          # 我們需要確保 hasattr 返回 False
          mocker.patch.object(mock_drive_service_optional, 'hasattr', return_value=False) # 這不對
          # 正確的方式是確保 mock_drive_service_optional 在 hasattr 檢查時表現得像沒有 delete_file
          # 最簡單的方法是重新 mock drive_service，使其不包含 delete_file
          # 但這裡我們假設 ReportIngestionService 內部是 hasattr(self.drive_service, 'delete_file')
          # 所以我們修改 drive_service 的行為
          mock_drive_service_no_delete = MagicMock(spec=GoogleDriveService)
          if hasattr(mock_drive_service_no_delete, 'delete_file'):
            del mock_drive_service_no_delete.delete_file # 從 spec=True 的 mock 中刪除方法
          report_ingestion_service.drive_service = mock_drive_service_no_delete


    result = await report_ingestion_service._archive_file_in_drive("file_id", "file_name", "proc_id", "orig_id")

    assert result == "delete_skipped_no_method"
    # 在這種情況下，delete_file 不會被調用
    # mock_drive_service_optional.delete_file.assert_not_called() # 這會失敗，因為我們刪除了方法

# --- ingest_single_drive_file 測試 ---

@pytest.mark.asyncio
async def test_ingest_single_drive_file_full_success(
    report_ingestion_service: ReportIngestionService,
    mock_drive_service_optional: AsyncMock,
    mock_dal: AsyncMock,
    mock_parsing_service: MagicMock,
    mock_gemini_service: AsyncMock,
    tmp_path # 用於模擬下載路徑
):
    """
    測試 ingest_single_drive_file 的完整成功路徑。
    包括下載、解析、存儲、分析、歸檔上傳、從 Drive 原始位置刪除。
    """
    file_id = "drive_file_id_001"
    file_name = "年度報告.pdf"
    original_folder = "inbox_folder"
    processed_folder = "processed_folder"
    temp_file_path = tmp_path / f"drive_{file_id}_{file_name}" # 模擬的下載路徑

    # 模擬依賴服務的成功行為
    mock_drive_service_optional.download_file.return_value = True
    mock_parsing_service.extract_text_from_file.return_value = "這是報告的文本內容。"
    mock_dal.insert_report_data.return_value = 1 # 返回模擬的報告資料庫 ID
    mock_gemini_service.analyze_report.return_value = {"summary": "AI 分析摘要"}
    mock_dal.update_report_analysis.return_value = True
    mock_drive_service_optional.upload_file.return_value = "archived_drive_file_id_001" # 歸檔後的 Drive ID
    mock_drive_service_optional.delete_file.return_value = True # 從原始位置刪除成功
    mock_dal.get_report_by_id.return_value = {"status": "內容已解析"} # 讓狀態更新邏輯通過

    # 使用 patch 來模擬 os.path.exists 和 os.remove，以驗證暫存檔案清理
    with patch('backend.services.report_ingestion_service.os.path.exists') as mock_exists, \
         patch('backend.services.report_ingestion_service.os.remove') as mock_remove:

        mock_exists.return_value = True # 模擬暫存檔案存在以進行清理

        result = await report_ingestion_service.ingest_single_drive_file(
            file_id, file_name, original_folder, processed_folder
        )

        assert result is True, "完整成功路徑應返回 True"

        # 驗證各個服務是否被正確調用
        mock_drive_service_optional.download_file.assert_called_once_with(file_id, str(temp_file_path))
        mock_parsing_service.extract_text_from_file.assert_called_once_with(str(temp_file_path))
        mock_dal.insert_report_data.assert_called_once()
        mock_gemini_service.analyze_report.assert_called_once_with("這是報告的文本內容。")
        mock_dal.update_report_analysis.assert_called_once()
        mock_drive_service_optional.upload_file.assert_called_once_with(
            local_file_path=str(temp_file_path),
            folder_id=processed_folder,
            file_name=file_name
        )
        mock_drive_service_optional.delete_file.assert_called_once_with(file_id) # 驗證原始檔案被刪除
        mock_dal.update_report_metadata.assert_called_once() # 驗證元數據更新

        # 驗證暫存檔案清理
        mock_exists.assert_called_with(str(temp_file_path)) # 檢查 finally 中的 exists
        mock_remove.assert_called_once_with(str(temp_file_path)) # 驗證 remove 被調用


@pytest.mark.asyncio
async def test_ingest_single_drive_file_drive_service_not_initialized(
    report_ingestion_service_no_drive: ReportIngestionService # 使用 drive_service 為 None 的 fixture
):
    """
    測試 ingest_single_drive_file：當 Drive Service 未初始化時，應快速失敗。
    """
    result = await report_ingestion_service_no_drive.ingest_single_drive_file(
        "file_id", "file_name", "orig_folder", "proc_folder"
    )
    assert result is False

@pytest.mark.asyncio
async def test_ingest_single_drive_file_download_fails(
    report_ingestion_service: ReportIngestionService,
    mock_drive_service_optional: AsyncMock,
    mock_dal: AsyncMock,
    tmp_path
):
    """
    測試 ingest_single_drive_file：當檔案下載失敗時。
    """
    file_id = "download_fail_id"
    file_name = "report_download_fail.doc"
    mock_drive_service_optional.download_file.return_value = False # 模擬下載失敗

    # 模擬 DAL 插入錯誤記錄
    mock_dal.insert_report_data.return_value = 99 # 假設插入錯誤記錄成功

    result = await report_ingestion_service.ingest_single_drive_file(
        file_id, file_name, "orig", "proc"
    )
    assert result is False
    mock_drive_service_optional.download_file.assert_called_once()
    # 驗證 DAL 是否被調用以記錄下載失敗
    args, kwargs = mock_dal.insert_report_data.call_args
    assert kwargs['status'] == "擷取錯誤(下載失敗)"
    assert kwargs['metadata'] == {"error": "download_failed", "drive_file_id": file_id}


@pytest.mark.asyncio
async def test_ingest_single_drive_file_parsing_fails(
    report_ingestion_service: ReportIngestionService,
    mock_drive_service_optional: AsyncMock,
    mock_parsing_service: MagicMock,
    mock_dal: AsyncMock,
    tmp_path
):
    """
    測試 ingest_single_drive_file：當檔案解析失敗 (ParsingService 返回錯誤標記)。
    """
    file_id = "parse_fail_id"
    file_name = "report_parse_fail.xyz"
    temp_file_path = tmp_path / f"drive_{file_id}_{file_name}"

    mock_drive_service_optional.download_file.return_value = True
    mock_parsing_service.extract_text_from_file.return_value = "[不支援的檔案類型: .xyz]" # 模擬解析失敗
    mock_dal.insert_report_data.return_value = 100 # 模擬 DAL 插入成功

    # 模擬 AI 分析不應該被調用，但歸檔流程應該繼續
    mock_drive_service_optional.upload_file.return_value = "archived_id_parse_fail"
    mock_drive_service_optional.delete_file.return_value = True
    mock_dal.get_report_by_id.return_value = {"status": "擷取錯誤(解析問題)"}


    result = await report_ingestion_service.ingest_single_drive_file(
        file_id, file_name, "orig", "proc"
    )

    assert result is True # 即使解析失敗，如果歸檔成功，整體可能算部分成功或按 True 處理（取決於業務邏輯，目前返回 True）
    mock_parsing_service.extract_text_from_file.assert_called_once_with(str(temp_file_path))
    args, kwargs = mock_dal.insert_report_data.call_args
    assert kwargs['status'] == "擷取錯誤(解析問題)"
    assert kwargs['content'] == "[不支援的檔案類型: .xyz]"
    report_ingestion_service.gemini_service.analyze_report.assert_not_called() # AI 分析應被跳過


@pytest.mark.asyncio
async def test_ingest_single_drive_file_dal_initial_insert_fails(
    report_ingestion_service: ReportIngestionService,
    mock_drive_service_optional: AsyncMock,
    mock_parsing_service: MagicMock, # 確保它返回成功以通過解析步驟
    mock_dal: AsyncMock,
    tmp_path
):
    """
    測試 ingest_single_drive_file：當 DataAccessLayer 初次儲存報告失敗時。
    """
    file_id = "dal_insert_fail_id"
    file_name = "report_dal_fail.txt"

    mock_drive_service_optional.download_file.return_value = True
    mock_parsing_service.extract_text_from_file.return_value = "一些有效內容"
    mock_dal.insert_report_data.return_value = None # 模擬 DAL 插入失敗

    result = await report_ingestion_service.ingest_single_drive_file(
        file_id, file_name, "orig", "proc"
    )
    assert result is False
    mock_dal.insert_report_data.assert_called_once() # 驗證 DAL 被調用
    # 後續的 AI 分析和歸檔不應發生
    report_ingestion_service.gemini_service.analyze_report.assert_not_called()
    mock_drive_service_optional.upload_file.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_single_drive_file_archive_upload_fails(
    report_ingestion_service: ReportIngestionService,
    mock_drive_service_optional: AsyncMock,
    mock_dal: AsyncMock,
    mock_parsing_service: MagicMock, # 確保解析成功
    mock_gemini_service: AsyncMock, # 確保分析被調用
    tmp_path
):
    """
    測試 ingest_single_drive_file：當檔案歸檔到 Drive 失敗 (上傳步驟)。
    """
    file_id = "archive_upload_fail_id"
    file_name = "report_archive_upload_fail.txt"
    report_db_id = 101

    mock_drive_service_optional.download_file.return_value = True
    mock_parsing_service.extract_text_from_file.return_value = "有效內容"
    mock_dal.insert_report_data.return_value = report_db_id
    mock_gemini_service.analyze_report.return_value = {"summary": "分析結果"} # 假設分析成功
    mock_drive_service_optional.upload_file.return_value = None # 模擬歸檔上傳失敗

    result = await report_ingestion_service.ingest_single_drive_file(
        file_id, file_name, "orig", "proc"
    )
    assert result is False
    mock_drive_service_optional.upload_file.assert_called_once()
    # 驗證資料庫狀態是否被更新為歸檔上傳失敗
    mock_dal.update_report_status.assert_called_with(report_db_id, "擷取錯誤(歸檔上傳失敗)")


@pytest.mark.asyncio
async def test_ingest_single_drive_file_archive_source_delete_fails(
    report_ingestion_service: ReportIngestionService,
    mock_drive_service_optional: AsyncMock,
    mock_dal: AsyncMock,
    mock_parsing_service: MagicMock,
    mock_gemini_service: AsyncMock,
    tmp_path
):
    """
    測試 ingest_single_drive_file：歸檔上傳成功，但從 Drive 原始位置刪除失敗。
    """
    file_id = "source_delete_fail_id"
    file_name = "report_source_delete_fail.txt"
    report_db_id = 102
    archived_drive_id = "archived_drive_id_102"

    mock_drive_service_optional.download_file.return_value = True
    mock_parsing_service.extract_text_from_file.return_value = "有效內容"
    mock_dal.insert_report_data.return_value = report_db_id
    mock_gemini_service.analyze_report.return_value = {"summary": "分析結果"}
    mock_drive_service_optional.upload_file.return_value = archived_drive_id # 歸檔上傳成功
    mock_drive_service_optional.delete_file.return_value = False # 模擬從原始位置刪除失敗
    mock_dal.get_report_by_id.return_value = {"status": "內容已解析"}


    result = await report_ingestion_service.ingest_single_drive_file(
        file_id, file_name, "orig_folder_id", "proc_folder_id"
    )
    assert result is True # 即使刪除失敗，整個操作可能仍視為成功，但狀態會不同

    # 驗證 DAL 更新狀態和元數據
    mock_dal.update_report_status.assert_any_call(report_db_id, "擷取部分成功(歸檔刪除失敗)")
    mock_dal.update_report_metadata.assert_called_with(
        report_db_id,
        {"archived_drive_file_id": archived_drive_id, "archive_status": "delete_from_inbox_failed"}
    )


@pytest.mark.asyncio
async def test_ingest_single_drive_file_general_exception_after_db_insert(
    report_ingestion_service: ReportIngestionService,
    mock_drive_service_optional: AsyncMock,
    mock_dal: AsyncMock,
    mock_parsing_service: MagicMock, # 讓解析成功
    tmp_path
):
    """
    測試 ingest_single_drive_file：在初次資料庫插入後，AI分析步驟之前發生未預期異常。
    """
    file_id = "general_exception_id"
    file_name = "report_general_exception.txt"
    report_db_id = 103

    mock_drive_service_optional.download_file.return_value = True
    mock_parsing_service.extract_text_from_file.return_value = "有效內容"
    mock_dal.insert_report_data.return_value = report_db_id
    # 模擬 _analyze_and_store_report (或其內部的 Gemini 調用) 拋出異常
    report_ingestion_service._analyze_and_store_report = AsyncMock(side_effect=Exception("模擬AI分析時的嚴重錯誤"))

    result = await report_ingestion_service.ingest_single_drive_file(
        file_id, file_name, "orig", "proc"
    )
    assert result is False
    # 驗證資料庫狀態是否被更新為處理異常
    mock_dal.update_report_status.assert_called_with(report_db_id, "擷取錯誤(處理異常)")


@pytest.mark.asyncio
async def test_ingest_single_drive_file_temp_file_cleanup(
    report_ingestion_service: ReportIngestionService,
    mock_drive_service_optional: AsyncMock, # 所有 Drive 操作都 mock 掉
    mock_dal: AsyncMock,
    mock_parsing_service: MagicMock,
    mock_gemini_service: AsyncMock,
    tmp_path,
    mocker
):
    """
    測試 ingest_single_drive_file：無論成功或失敗，都應嘗試清理本地臨時檔案。
    """
    file_id = "cleanup_test_id"
    file_name = "cleanup_report.txt"
    # 模擬的下載路徑，確保它在 tmp_path 下
    # ingest_single_drive_file 內部會構造這個路徑
    # local_download_path = tmp_path / f"drive_{file_id}_{file_name}"
    # 為了讓 os.path.exists(local_download_path) 在 finally 中返回 True，我們需要 mock 它
    # 或者確保下載步驟 "成功" (即使是 mock 的成功)

    mock_os_path_exists = mocker.patch('backend.services.report_ingestion_service.os.path.exists')
    mock_os_remove = mocker.patch('backend.services.report_ingestion_service.os.remove')

    # 場景1：成功路徑
    mock_drive_service_optional.download_file.return_value = True
    mock_parsing_service.extract_text_from_file.return_value = "成功內容"
    mock_dal.insert_report_data.return_value = 201
    mock_gemini_service.analyze_report.return_value = {"summary": "分析成功"}
    mock_drive_service_optional.upload_file.return_value = "archived_id_201"
    mock_drive_service_optional.delete_file.return_value = True
    mock_dal.get_report_by_id.return_value = {"status": "內容已解析"}
    mock_os_path_exists.return_value = True # 模擬檔案在 finally 檢查時存在

    await report_ingestion_service.ingest_single_drive_file(file_id, file_name, "orig", "proc")
    mock_os_remove.assert_called_once() # 驗證 os.remove 被調用

    # 重置 Mocks 以用於下一個場景
    mock_os_path_exists.reset_mock()
    mock_os_remove.reset_mock()
    mock_drive_service_optional.reset_mock() # 重置所有 drive service mocks
    mock_dal.reset_mock()
    # ... 其他需要重置的 mock

    # 場景2：下載失敗路徑
    mock_drive_service_optional.download_file.return_value = False # 模擬下載失敗
    # 確保 insert_report_data 在下載失敗時仍被調用以記錄錯誤
    mock_dal.insert_report_data.return_value = 202
    mock_os_path_exists.return_value = True # 假設下載可能創建了一個空檔案或部分檔案

    await report_ingestion_service.ingest_single_drive_file(file_id + "_fail", file_name + "_fail", "orig", "proc")
    # 即使下載失敗，如果 local_download_path 被認為存在，也應嘗試清理
    # 注意：如果 download_file 失敗時不創建文件，則 mock_os_path_exists 應返回 False，remove 不會被調用。
    # 這裡的假設是，即使 download_file 返回 False，也可能已創建了文件。
    # 根據 ingest_single_drive_file 中 finally 塊的邏輯，只要路徑存在就會嘗試刪除。
    mock_os_remove.assert_called_once()


# --- ingest_reports_from_drive_folder 測試 ---

@pytest.mark.asyncio
async def test_ingest_reports_from_drive_folder_no_drive_service(
    report_ingestion_service_no_drive: ReportIngestionService # 使用 drive_service 為 None 的 fixture
):
    """
    測試 ingest_reports_from_drive_folder：當 Drive Service 未初始化時，應返回 (0, 0)。
    """
    success, fail = await report_ingestion_service_no_drive.ingest_reports_from_drive_folder("inbox", "processed")
    assert success == 0
    assert fail == 0

@pytest.mark.asyncio
async def test_ingest_reports_from_drive_folder_list_files_error(
    report_ingestion_service: ReportIngestionService,
    mock_drive_service_optional: AsyncMock
):
    """
    測試 ingest_reports_from_drive_folder：當 list_files (假設為 list_files) 出錯時。
    """
    mock_drive_service_optional.list_files.side_effect = Exception("模擬列出檔案失敗")

    success, fail = await report_ingestion_service.ingest_reports_from_drive_folder("inbox", "processed")
    assert success == 0
    assert fail == 0
    mock_drive_service_optional.list_files.assert_called_once_with("inbox")


@pytest.mark.asyncio
async def test_ingest_reports_from_drive_folder_no_files_found(
    report_ingestion_service: ReportIngestionService,
    mock_drive_service_optional: AsyncMock
):
    """
    測試 ingest_reports_from_drive_folder：當 Drive 中沒有找到任何檔案時。
    """
    mock_drive_service_optional.list_files.return_value = [] # 返回空列表

    success, fail = await report_ingestion_service.ingest_reports_from_drive_folder("inbox", "processed")
    assert success == 0
    assert fail == 0
    mock_drive_service_optional.list_files.assert_called_once_with("inbox")

@pytest.mark.asyncio
async def test_ingest_reports_from_drive_folder_partial_success(
    report_ingestion_service: ReportIngestionService,
    mock_drive_service_optional: AsyncMock,
    mock_dal: AsyncMock,
    mocker # 用於 mock ingest_single_drive_file
):
    """
    測試 ingest_reports_from_drive_folder：部分檔案成功，部分檔案失敗。
    """
    mock_drive_service_optional.list_files.return_value = [
        {"id": "file1", "name": "report1.txt"},
        {"id": "file2", "name": "report2.txt"}, # 這個會失敗
        {"id": "file3", "name": "report3.txt"},
    ]
    # 模擬 check_report_exists_by_source_path 總是返回 False (非重複)
    mock_dal.check_report_exists_by_source_path.return_value = False

    # mock ingest_single_drive_file 的行為
    async def mock_ingest_single(file_id, file_name, orig_folder, proc_folder):
        if file_id == "file2":
            return False # 模擬 file2 處理失敗
        return True # 其他成功

    mocker.patch.object(report_ingestion_service, 'ingest_single_drive_file', side_effect=mock_ingest_single)

    success, fail = await report_ingestion_service.ingest_reports_from_drive_folder("inbox", "processed")

    assert success == 2
    assert fail == 1
    assert report_ingestion_service.ingest_single_drive_file.call_count == 3


@pytest.mark.asyncio
async def test_ingest_reports_from_drive_folder_skips_existing(
    report_ingestion_service: ReportIngestionService,
    mock_drive_service_optional: AsyncMock,
    mock_dal: AsyncMock,
    mocker
):
    """
    測試 ingest_reports_from_drive_folder：跳過資料庫中已存在的報告。
    """
    mock_drive_service_optional.list_files.return_value = [
        {"id": "file1_exist", "name": "existing_report.txt"},
        {"id": "file2_new", "name": "new_report.txt"},
    ]

    async def mock_check_exists(source_path):
        if source_path == "drive_id:file1_exist":
            return True # 模擬 file1 已存在
        return False
    mock_dal.check_report_exists_by_source_path.side_effect = mock_check_exists

    mock_ingest_single = mocker.patch.object(report_ingestion_service, 'ingest_single_drive_file', new_callable=AsyncMock)
    mock_ingest_single.return_value = True # 假設新檔案處理成功

    success, fail = await report_ingestion_service.ingest_reports_from_drive_folder("inbox", "processed")

    assert success == 1 # 只有 new_report.txt 被處理
    assert fail == 0
    mock_dal.check_report_exists_by_source_path.assert_any_call("drive_id:file1_exist")
    mock_dal.check_report_exists_by_source_path.assert_any_call("drive_id:file2_new")
    # ingest_single_drive_file 只應為 file2_new 被調用
    report_ingestion_service.ingest_single_drive_file.assert_called_once_with(
        "file2_new", "new_report.txt", "inbox", "processed"
    )


# --- ingest_uploaded_file 測試 ---

@pytest.mark.asyncio
async def test_ingest_uploaded_file_success(
    report_ingestion_service: ReportIngestionService,
    mock_parsing_service: MagicMock,
    mock_dal: AsyncMock,
    mock_gemini_service: AsyncMock
):
    """
    測試 ingest_uploaded_file 的完整成功路徑。
    """
    file_name = "uploaded_report.txt"
    file_path = "/tmp/uploaded_report.txt" # 僅為標識，實際不讀取此路徑
    report_content = "這是上傳檔案的內容。"
    db_id = 301

    mock_parsing_service.extract_text_from_file.return_value = report_content
    mock_dal.insert_report_data.return_value = db_id
    mock_gemini_service.analyze_report.return_value = {"summary": "AI分析完成"}

    result_db_id = await report_ingestion_service.ingest_uploaded_file(file_name, file_path)

    assert result_db_id == db_id
    mock_parsing_service.extract_text_from_file.assert_called_once_with(file_path)
    mock_dal.insert_report_data.assert_called_once()
    args_insert, kwargs_insert = mock_dal.insert_report_data.call_args
    assert kwargs_insert['original_filename'] == file_name
    assert kwargs_insert['content'] == report_content
    assert kwargs_insert['source_path'] == f"upload:{file_name}"
    assert kwargs_insert['status'] == "內容已解析"
    mock_gemini_service.analyze_report.assert_called_once_with(report_content)
    mock_dal.update_report_analysis.assert_called_once_with(db_id, json.dumps({"summary": "AI分析完成"}, ensure_ascii=False), "分析完成")


@pytest.mark.asyncio
async def test_ingest_uploaded_file_parsing_fails(
    report_ingestion_service: ReportIngestionService,
    mock_parsing_service: MagicMock,
    mock_dal: AsyncMock,
    mock_gemini_service: AsyncMock # 確保 AI 分析不被調用
):
    """
    測試 ingest_uploaded_file：當檔案解析失敗時。
    """
    file_name = "parse_fail_upload.dat"
    file_path = "/tmp/parse_fail_upload.dat"
    db_id = 302

    mock_parsing_service.extract_text_from_file.return_value = "[不支援的檔案類型: .dat]"
    mock_dal.insert_report_data.return_value = db_id # 即使解析失敗，也應該記錄

    result_db_id = await report_ingestion_service.ingest_uploaded_file(file_name, file_path)

    assert result_db_id == db_id
    args_insert, kwargs_insert = mock_dal.insert_report_data.call_args
    assert kwargs_insert['status'] == "擷取錯誤(解析問題)"
    mock_gemini_service.analyze_report.assert_not_called() # AI分析不應被調用

@pytest.mark.asyncio
async def test_ingest_uploaded_file_dal_insert_fails(
    report_ingestion_service: ReportIngestionService,
    mock_parsing_service: MagicMock,
    mock_dal: AsyncMock
):
    """
    測試 ingest_uploaded_file：當 DataAccessLayer 儲存失敗時。
    """
    mock_parsing_service.extract_text_from_file.return_value = "一些內容"
    mock_dal.insert_report_data.return_value = None # 模擬 DAL 失敗

    result_db_id = await report_ingestion_service.ingest_uploaded_file("dal_fail.txt", "/tmp/dal_fail.txt")
    assert result_db_id is None

@pytest.mark.asyncio
async def test_ingest_uploaded_file_analyze_fails(
    report_ingestion_service: ReportIngestionService,
    mock_parsing_service: MagicMock,
    mock_dal: AsyncMock,
    mock_gemini_service: AsyncMock
):
    """
    測試 ingest_uploaded_file：內容解析和儲存成功，但 AI 分析失敗。
    """
    file_name = "ai_fail_upload.txt"
    file_path = "/tmp/ai_fail_upload.txt"
    report_content = "待分析內容"
    db_id = 303

    mock_parsing_service.extract_text_from_file.return_value = report_content
    mock_dal.insert_report_data.return_value = db_id
    mock_gemini_service.analyze_report.return_value = {"錯誤": "AI分析時發生錯誤"} # AI 服務返回錯誤

    result_db_id = await report_ingestion_service.ingest_uploaded_file(file_name, file_path)

    assert result_db_id == db_id # 即使 AI 分析失敗，初步插入成功，應返回 ID
    mock_gemini_service.analyze_report.assert_called_once_with(report_content)
    # 驗證 DAL 的 update_report_analysis 被調用以記錄錯誤
    args_update, kwargs_update = mock_dal.update_report_analysis.call_args
    assert args_update[0] == db_id
    assert json.loads(args_update[1])["錯誤"] == "AI分析時發生錯誤"
    assert args_update[2] == "分析失敗"

@pytest.mark.asyncio
async def test_ingest_uploaded_file_general_exception(
    report_ingestion_service: ReportIngestionService,
    mock_parsing_service: MagicMock,
    mock_dal: AsyncMock # 用於驗證是否嘗試更新錯誤狀態
):
    """
    測試 ingest_uploaded_file：當處理過程中發生未預期異常時。
    """
    file_name = "exception_upload.txt"
    file_path = "/tmp/exception_upload.txt"
    simulated_error = Exception("模擬上傳處理中發生嚴重錯誤")

    # 讓解析服務在被調用時拋出異常
    mock_parsing_service.extract_text_from_file.side_effect = simulated_error

    result_db_id = await report_ingestion_service.ingest_uploaded_file(file_name, file_path)
    assert result_db_id is None

    # 驗證是否沒有插入任何報告數據（因為錯誤發生在插入之前）
    mock_dal.insert_report_data.assert_not_called()
    # 驗證是否沒有嘗試更新分析（因為錯誤發生在AI分析之前或期間）
    mock_dal.update_report_analysis.assert_not_called()

    # 如果異常發生在 DAL insert 之後，DAL update 會被調用
    mock_dal.reset_mock() # 重置 DAL mock
    mock_parsing_service.extract_text_from_file.side_effect = None # 讓解析成功
    mock_parsing_service.extract_text_from_file.return_value = "some content"
    mock_dal.insert_report_data.return_value = 304 # 模擬插入成功
    # 讓 _analyze_and_store_report (或其內部的 gemini_service) 拋出錯誤
    report_ingestion_service._analyze_and_store_report = AsyncMock(side_effect=simulated_error)

    result_db_id = await report_ingestion_service.ingest_uploaded_file(file_name, file_path)
    assert result_db_id is None # 即使插入了，但如果後續失敗，這裡的實現是返回None

    mock_dal.insert_report_data.assert_called_once() # 這次插入被調用
    # 驗證 update_report_analysis 被調用以記錄錯誤
    args_update, kwargs_update = mock_dal.update_report_analysis.call_args
    assert args_update[0] == 304
    assert json.loads(args_update[1])["錯誤"] == f"處理上傳檔案時發生意外: {simulated_error}"
    assert args_update[2] == "擷取錯誤(系統異常)"
