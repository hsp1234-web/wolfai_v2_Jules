# -*- coding: utf-8 -*-
import pytest
from unittest.mock import mock_open # mocker comes from pytest-mock
from backend.services.parsing_service import ParsingService

@pytest.fixture
def parsing_service() -> ParsingService:
    """
    提供一個 ParsingService 的實例作為測試固件。
    """
    return ParsingService()

def test_get_file_extension(parsing_service: ParsingService):
    """
    測試 _get_file_extension 方法是否能正確處理不同的大小寫和檔名。
    """
    assert parsing_service._get_file_extension("report.txt") == ".txt"
    assert parsing_service._get_file_extension("Document.PDF") == ".pdf"
    assert parsing_service._get_file_extension("archive.tar.gz") == ".gz"
    assert parsing_service._get_file_extension("no_extension") == ""
    assert parsing_service._get_file_extension(".bashrc") == ".bashrc" # Hidden file with extension

def test_extract_text_from_txt_file(parsing_service: ParsingService, mocker):
    """
    測試從 .txt 檔案中提取文字。
    """
    mock_content = "這是純文字檔案的內容。\n包含多行。"
    # 使用 mocker.patch 來模擬 builtins.open
    mocker.patch('builtins.open', mocker.mock_open(read_data=mock_content))

    extracted_text = parsing_service.extract_text_from_file("dummy/path/to/file.txt")

    assert extracted_text == mock_content, "提取的文字內容與預期不符。"

def test_extract_text_from_md_file(parsing_service: ParsingService, mocker):
    """
    測試從 .md 檔案中提取文字。
    """
    mock_content = "# Markdown 標題\n\n這是一些 markdown *內容*。"
    mocker.patch('builtins.open', mocker.mock_open(read_data=mock_content))

    extracted_text = parsing_service.extract_text_from_file("any/file.md")

    assert extracted_text == mock_content, "提取的 Markdown 內容與預期不符。"

def test_extract_text_unsupported_extension(parsing_service: ParsingService):
    """
    測試不支援的副檔名是否返回預期的中文提示。
    """
    # 對於不支援的擴展名，我們預期得到一個包含擴展名的提示訊息
    expected_message_part_docx = "[不支援的檔案類型: .docx]" # Based on current implementation
    # Actually, current implementation for docx returns a specific message, let's test that.
    expected_message_docx = "[.docx 檔案內容解析功能待實現]"
    assert parsing_service.extract_text_from_file("report.docx") == expected_message_docx

    expected_message_pdf = "[.pdf 檔案內容解析功能待實現]"
    assert parsing_service.extract_text_from_file("report.pdf") == expected_message_pdf

    expected_message_custom = "[不支援的檔案類型: .xyz]"
    assert parsing_service.extract_text_from_file("archive.xyz") == expected_message_custom

def test_extract_text_file_not_found(parsing_service: ParsingService, mocker):
    """
    測試當檔案未找到時，服務是否能優雅處理並返回中文錯誤訊息。
    """
    # 模擬 open 拋出 FileNotFoundError
    mocker.patch('builtins.open', side_effect=FileNotFoundError("模擬：檔案不存在"))

    # 預期返回的錯誤訊息格式
    # Based on current implementation: "[檔案內容解析錯誤: 模擬：檔案不存在]"
    expected_error_message = "[檔案內容解析錯誤: 模擬：檔案不存在]"
    extracted_text = parsing_service.extract_text_from_file("non_existent_file.txt")

    assert extracted_text == expected_error_message, "檔案未找到時的錯誤訊息不符合預期。"

def test_extract_text_read_error(parsing_service: ParsingService, mocker):
    """
    測試當檔案讀取時發生IO錯誤，服務是否能優雅處理並返回中文錯誤訊息。
    """
    mocker.patch('builtins.open', side_effect=IOError("模擬：讀取錯誤"))

    expected_error_message = "[檔案內容解析錯誤: 模擬：讀取錯誤]"
    extracted_text = parsing_service.extract_text_from_file("readable_file.txt")

    assert extracted_text == expected_error_message, "檔案讀取錯誤時的錯誤訊息不符合預期。"

# Future tests could include:
# - Test with different encodings if the service is expected to handle them.
# - Test with very large files (if applicable, though unit tests usually avoid this).
# - Test for specific content parsing for .docx and .pdf once implemented.
