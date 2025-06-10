# -*- coding: utf-8 -*-
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch # For mocking async methods and classes

# Assuming settings are managed via a singleton or can be easily mocked.
# If backend.config.settings is the way, we might need to mock that.
from backend.config import Settings # To mock its instance
from backend.services.gemini_service import GeminiService
from pydantic import SecretStr


@pytest.fixture
def mock_settings_no_api_key(mocker):
    """模擬一個沒有設定 COLAB_GOOGLE_API_KEY 的 Settings 物件。"""
    mock = Settings(COLAB_GOOGLE_API_KEY=None)
    mocker.patch('backend.services.gemini_service.settings', mock) # Patch where 'settings' is imported in gemini_service
    return mock

@pytest.fixture
def mock_settings_with_api_key(mocker):
    """模擬一個設定了有效 COLAB_GOOGLE_API_KEY 的 Settings 物件。"""
    mock = Settings(COLAB_GOOGLE_API_KEY=SecretStr("test_api_key_12345"))
    mocker.patch('backend.services.gemini_service.settings', mock)
    return mock

@pytest.fixture
def mock_genai_configure(mocker):
    """模擬 google.generativeai.configure。"""
    return mocker.patch('google.generativeai.configure')

@pytest.fixture
def mock_generative_model(mocker):
    """模擬 google.generativeai.GenerativeModel 及其異步方法。"""
    mock_model_instance = MagicMock()
    # Mock the async method generate_content_async
    mock_model_instance.generate_content_async = AsyncMock()

    # Patch the class to return our mock_model_instance when instantiated
    mocker.patch('google.generativeai.GenerativeModel', return_value=mock_model_instance)
    return mock_model_instance


# --- Test Cases ---

def test_gemini_service_init_no_api_key(mock_settings_no_api_key, mock_genai_configure):
    """測試 GeminiService 初始化：當未提供 API 金鑰時。"""
    service = GeminiService()
    assert not service.is_configured, "未提供金鑰時，is_configured 應為 False。"
    mock_genai_configure.assert_not_called() # genai.configure 不應被調用

def test_gemini_service_init_with_api_key(mock_settings_with_api_key, mock_genai_configure):
    """測試 GeminiService 初始化：當提供了 API 金鑰時。"""
    service = GeminiService()
    assert service.is_configured, "提供金鑰時，is_configured 應為 True。"
    mock_genai_configure.assert_called_once_with(api_key="test_api_key_12345")

def test_gemini_service_init_configure_failure(mock_settings_with_api_key, mock_genai_configure):
    """測試 GeminiService 初始化：當 genai.configure 拋出例外時。"""
    mock_genai_configure.side_effect = Exception("模擬配置失敗")
    service = GeminiService()
    assert not service.is_configured, "配置失敗時，is_configured 應為 False。"


@pytest.mark.asyncio
async def test_summarize_text_not_configured(mock_settings_no_api_key):
    """測試 summarize_text：當服務未配置 (無API金鑰) 時。"""
    service = GeminiService() # is_configured will be False
    result = await service.summarize_text("一些文字")
    assert "服務未配置" in result, "未配置時應返回提示訊息。"

@pytest.mark.asyncio
async def test_summarize_text_empty_input(mock_settings_with_api_key, mock_genai_configure):
    """測試 summarize_text：當輸入文字為空時。"""
    service = GeminiService() # is_configured will be True
    result = await service.summarize_text("")
    assert "輸入文字為空" in result, "輸入為空時應返回提示訊息。"
    result_none = await service.summarize_text(None)
    assert "輸入文字為空" in result_none

@pytest.mark.asyncio
async def test_summarize_text_success(mock_settings_with_api_key, mock_genai_configure, mock_generative_model):
    """測試 summarize_text：API 呼叫成功。"""
    service = GeminiService()

    # 模擬 API 回應
    mock_response = MagicMock()
    mock_response.parts = [MagicMock(text="這是摘要結果。")] # Simulate structure with parts
    mock_response.text = "這是摘要結果。" # Also simulate direct .text for robustness
    mock_generative_model.generate_content_async.return_value = mock_response

    text_to_summarize = "這是一段需要摘要的長文字..."
    summary = await service.summarize_text(text_to_summarize)

    assert summary == "這是摘要結果。", "摘要結果與預期不符。"
    mock_generative_model.generate_content_async.assert_called_once()
    # 可以進一步檢查傳遞給 generate_content_async 的 prompt 是否符合預期

@pytest.mark.asyncio
async def test_summarize_text_api_failure_with_retry(mock_settings_with_api_key, mock_genai_configure, mock_generative_model):
    """測試 summarize_text：API 呼叫失敗後重試成功。"""
    service = GeminiService()

    # 模擬 API 第一次失敗，第二次成功
    mock_success_response = MagicMock(text="重試後的摘要。")
    mock_success_response.parts = [MagicMock(text="重試後的摘要。")]

    mock_generative_model.generate_content_async.side_effect = [
        Exception("模擬第一次API錯誤"),
        mock_success_response
    ]

    summary = await service.summarize_text("測試重試文字", max_retries=1, retry_delay=0.1) # Short delay for test

    assert summary == "重試後的摘要。"
    assert mock_generative_model.generate_content_async.call_count == 2, "API 應被調用兩次 (1次原始 + 1次重試)。"

@pytest.mark.asyncio
async def test_summarize_text_api_failure_max_retries(mock_settings_with_api_key, mock_genai_configure, mock_generative_model):
    """測試 summarize_text：API 呼叫達到最大重試次數後失敗。"""
    service = GeminiService()

    mock_generative_model.generate_content_async.side_effect = Exception("模擬持續API錯誤")

    result = await service.summarize_text("測試持續失敗文字", max_retries=2, retry_delay=0.1)

    assert "API請求錯誤" in result, "達到最大重試次數後應返回錯誤訊息。"
    assert mock_generative_model.generate_content_async.call_count == 3, "API 應被調用三次 (1次原始 + 2次重試)。"

# ---- analyze_report tests ----

@pytest.mark.asyncio
async def test_analyze_report_not_configured(mock_settings_no_api_key):
    """測試 analyze_report：當服務未配置 (無API金鑰) 時。"""
    service = GeminiService()
    result = await service.analyze_report("一些報告內容")
    assert isinstance(result, dict) and "錯誤" in result
    assert "服務未配置" in result["錯誤"], "未配置時應返回包含錯誤的字典。"

@pytest.mark.asyncio
async def test_analyze_report_success_json_output(mock_settings_with_api_key, mock_genai_configure, mock_generative_model):
    """測試 analyze_report：API 呼叫成功並返回有效 JSON。"""
    service = GeminiService()

    expected_dict = {"main_findings": "主要發現A", "potential_risks": "風險B", "suggested_actions": "行動C"}
    mock_response_text = json.dumps(expected_dict, ensure_ascii=False)

    mock_api_response = MagicMock()
    mock_api_response.parts = [MagicMock(text=mock_response_text)]
    mock_api_response.text = mock_response_text # Fallback
    mock_generative_model.generate_content_async.return_value = mock_api_response

    analysis = await service.analyze_report("這是報告內容...")

    assert analysis == expected_dict, "分析結果與預期不符。"

@pytest.mark.asyncio
async def test_analyze_report_json_decode_error(mock_settings_with_api_key, mock_genai_configure, mock_generative_model):
    """測試 analyze_report：API 返回的文字不是有效的 JSON。"""
    service = GeminiService()

    invalid_json_text = "這不是JSON格式。"
    mock_api_response = MagicMock(text=invalid_json_text)
    mock_api_response.parts = [MagicMock(text=invalid_json_text)]
    mock_generative_model.generate_content_async.return_value = mock_api_response

    result = await service.analyze_report("報告內容...")

    assert isinstance(result, dict) and "錯誤" in result
    assert "JSON解析錯誤" in result["錯誤"], "無效JSON時應返回包含JSON解析錯誤的字典。"
    if "原始回應" in result: # Check if original response is included
         assert result["原始回應"] == invalid_json_text

@pytest.mark.asyncio
async def test_analyze_report_api_failure_max_retries(mock_settings_with_api_key, mock_genai_configure, mock_generative_model):
    """測試 analyze_report：API 呼叫達到最大重試次數後失敗。"""
    service = GeminiService()

    mock_generative_model.generate_content_async.side_effect = Exception("模擬持續API錯誤")

    result = await service.analyze_report("測試持續失敗的報告", max_retries=1, retry_delay=0.1)

    assert isinstance(result, dict) and "錯誤" in result
    assert "API請求錯誤" in result["錯誤"], "達到最大重試次數後應返回包含錯誤的字典。"
    assert mock_generative_model.generate_content_async.call_count == 2

@pytest.mark.asyncio
async def test_analyze_report_handles_markdown_json(mock_settings_with_api_key, mock_genai_configure, mock_generative_model):
    """測試 analyze_report 是否能處理 Markdown 包裹的 JSON。"""
    service = GeminiService()
    expected_dict = {"key": "value"}
    markdown_json = f"一些文字...\n```json\n{json.dumps(expected_dict)}\n```\n其他文字..."

    mock_api_response = MagicMock(text=markdown_json)
    mock_api_response.parts = [MagicMock(text=markdown_json)]
    mock_generative_model.generate_content_async.return_value = mock_api_response

    analysis = await service.analyze_report("報告")
    assert analysis == expected_dict

@pytest.mark.asyncio
async def test_summarize_text_blocked_response(mock_settings_with_api_key, mock_genai_configure, mock_generative_model):
    """測試 summarize_text：API 回應被阻擋。"""
    service = GeminiService()

    mock_response = MagicMock()
    mock_response.parts = [] # No parts with text
    mock_response.text = None  # No direct text
    mock_response.prompt_feedback = MagicMock(block_reason="SAFETY", block_reason_message="因安全原因被阻擋")
    mock_generative_model.generate_content_async.return_value = mock_response

    summary = await service.summarize_text("可能觸發安全設定的文字")

    assert "請求因 因安全原因被阻擋 被阻擋" in summary, "應返回阻擋原因。"

# Add more tests for analyze_report for different scenarios like empty content, API failures etc.
# similar to summarize_text tests.
