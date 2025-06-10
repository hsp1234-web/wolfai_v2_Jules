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

def test_extract_text_file_not_found(parsing_service: ParsingService):
    """
    測試當傳入一個不存在的檔案路徑時，服務是否返回預期的「檔案未找到」錯誤訊息。
    """
    non_existent_path = "絕對不可能存在的路徑/some_random_name_blah_blah.txt"
    # 服務內部會先檢查 os.path.exists，然後在 open 時可能再次失敗
    # 根據 parsing_service.py 的邏輯，如果 os.path.exists(file_path) 為 False,
    # file_size 會是 None。如果副檔名是 .txt 或 .md, 接下來的 open() 會觸發 FileNotFoundError。
    # 該 FileNotFoundError 會被捕獲並返回 f"[檔案未找到: {file_path}]"

    # 清理：確保測試前此路徑確實不存在（儘管其名稱已暗示）
    if os.path.exists(non_existent_path):
        pytest.skip(f"測試路徑 {non_existent_path} 意外存在，跳過此測試。")

    expected_message = f"[檔案未找到: {non_existent_path}]"
    extracted_text = parsing_service.extract_text_from_file(non_existent_path)

    # 由於 parsing_service.py 中對 file_size 的獲取邏輯,
    # 以及後續對 open 的調用都可能感知到檔案不存在,
    # 我們主要關心最終的輸出是否符合預期。
    # parsing_service.py 的 FileNotFoundError 異常處理塊決定了最終的錯誤消息格式。
    assert extracted_text == expected_message, f"檔案未找到時的錯誤訊息不符合預期。收到: {extracted_text}"


def test_extract_text_from_txt_with_special_chars(parsing_service: ParsingService, tmp_path):
    """
    測試從 .txt 檔案中提取包含繁體中文和特殊符號的文字。
    使用 tmp_path fixture 來創建臨時檔案。
    """
    file_path = tmp_path / "test_special_chars.txt"
    # 包含繁體中文、英文、數字、常見及不常見符號
    mock_content = "這是繁體中文測試，English text, 12345。\n包含符號：，。？！（）「」《》😊🚀🔥"

    file_path.write_text(mock_content, encoding='utf-8')

    extracted_text = parsing_service.extract_text_from_file(str(file_path))
    assert extracted_text == mock_content, "提取的包含特殊字符的 .txt 內容與預期不符。"

def test_extract_text_from_md_with_special_chars(parsing_service: ParsingService, tmp_path):
    """
    測試從 .md 檔案中提取包含繁體中文和特殊符號的文字。
    使用 tmp_path fixture 來創建臨時檔案。
    """
    file_path = tmp_path / "test_special_chars.md"
    mock_content = "# 測試標題\n\n這是繁體中文段落，包含 *Markdown* 語法與符號：【】℃¥§©️\nEmoji: 😂👍🎉"

    file_path.write_text(mock_content, encoding='utf-8')

    extracted_text = parsing_service.extract_text_from_file(str(file_path))
    assert extracted_text == mock_content, "提取的包含特殊字符的 .md 內容與預期不符。"

def test_extract_text_with_unicode_decode_error(parsing_service: ParsingService, tmp_path, mocker):
    """
    測試當 .txt 檔案內容無法以 UTF-8 解碼時，服務是否返回預期的錯誤訊息。
    """
    file_path = tmp_path / "test_bad_encoding.txt"
    # 使用 GBK 編碼寫入一些中文字，當服務以 UTF-8 讀取時會產生 UnicodeDecodeError
    gbk_content_bytes = "你好世界".encode('gbk')
    file_path.write_bytes(gbk_content_bytes)

    # 預期 parsing_service.py 中的 `except Exception as e:` 會捕獲此錯誤
    # 並返回 f"[檔案內容解析錯誤: {str(e)}]"
    # 具體的錯誤訊息可能類似 "'utf-8' codec can't decode byte 0xb3 in position 2: invalid start byte"
    extracted_text = parsing_service.extract_text_from_file(str(file_path))

    assert extracted_text.startswith("[檔案內容解析錯誤:"), "應返回解析錯誤的通用前綴。"
    assert "'utf-8' codec can't decode byte" in extracted_text, "錯誤訊息應包含 UTF-8 解碼失敗的具體原因。"

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
