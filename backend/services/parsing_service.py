# -*- coding: utf-8 -*-
import os
import logging

logger = logging.getLogger(__name__)

class ParsingService:
    """
    提供從不同類型檔案中提取純文字內容的服務。

    該服務的主要職責是識別檔案類型，並根據檔案類型調用相應的解析邏輯
    來提取可讀的文字資訊。它的目標是將各種文件格式的內容轉換為統一的
    純文字格式，以便後續的處理、分析或索引。

    核心功能包括：
    - **檔案類型識別**: 通過檔案副檔名判斷檔案的類型。
    - **文字提取**:
        - 對於純文字檔案 (.txt, .md)，直接讀取其內容。
        - 對於其他複雜檔案格式 (如 .docx, .pdf)，目前會返回一個提示訊息，
          表明該類型檔案的解析功能「待實現」。未來的版本中，將會集成
          專門的函式庫 (如 python-docx, PyPDF2) 來實現這些格式的內容提取。
    - **錯誤處理與日誌記錄**:
        - 處理檔案不存在、無法讀取或不支持的檔案類型等情況。
        - 記錄詳細的操作日誌，包括檔案路徑、類型、大小以及解析狀態。

    該服務旨在提供一個集中的、可擴展的解決方案，用於處理應用程式中
    所有與檔案內容解析相關的需求。
    """

    def __init__(self):
        """
        初始化 ParsingService。

        這個構造函數目前非常簡單，主要執行以下操作：
        1. 記錄一條日誌訊息，表明 ParsingService 的一個實例已被創建和初始化。

        在未來的版本中，如果服務需要依賴外部資源、配置特定的解析器實例或
        執行任何其他預備步驟，這些邏輯將會被添加到此構造函數中。
        例如，可能會在這裡預先加載某些大型的解析模型或設定。
        """
        # 記錄服務初始化的日誌訊息，有助於追蹤服務的生命週期。
        logger.info(
            "文字解析服務 (ParsingService) 已初始化。",
            extra={"props": {"service_name": "ParsingService", "status": "initialized"}}
        )

    def _get_file_extension(self, file_name: str) -> str:
        """
        獲取檔案的小寫副檔名。
        """
        # 使用 os.path.splitext 分割檔案名和副檔名，[1] 取副檔名部分，並轉換為小寫
        return os.path.splitext(file_name)[1].lower()

    def extract_text_from_file(self, file_path: str) -> str:
        """
        從指定的本地檔案路徑中提取純文字內容。

        此方法會首先嘗試確定檔案的副檔名和大小以用於日誌記錄。
        然後，它會根據檔案的副檔名選擇合適的解析策略：
        -   對於 `.txt` 和 `.md` (Markdown) 檔案，它會直接以 UTF-8 編碼讀取檔案內容。
        -   對於 `.docx` 和 `.pdf` 檔案，目前版本會返回一個提示訊息，
            表明這些檔案類型的解析功能「待實現」。
        -   對於其他所有不支援的副檔名，會返回一個「不支援的檔案類型」的訊息。

        錯誤處理：
        -   如果檔案在指定路徑下未找到 (`FileNotFoundError`)，會返回相應的錯誤訊息。
        -   如果在檔案讀取或處理過程中發生其他任何異常 (`Exception`)，會返回
            一個通用的「檔案內容解析錯誤」訊息，並將具體錯誤記錄到日誌中。

        Args:
            file_path (str): 要從中提取文字內容的本地檔案的完整路徑。

        Returns:
            str: 提取出的純文字內容。如果檔案不受支援、未找到或解析過程中發生錯誤，
                 則返回包含錯誤或提示信息的字串。
        """
        # 獲取檔案的副檔名，用於後續判斷處理邏輯
        file_extension = self._get_file_extension(file_path)
        content = "" # 初始化內容字串

        # 嘗試獲取檔案大小以用於日誌記錄，同時處理路徑無效或檔案不存在的早期錯誤
        file_size = None
        try:
            # 在獲取大小前檢查檔案是否存在，避免因路徑問題導致 getsize 拋出異常
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
        except OSError: # 捕獲 os.path.exists 或 os.path.getsize 可能引發的作業系統相關錯誤
             logger.warning(f"無法獲取檔案大小或檢查檔案是否存在: {file_path}", extra={"props": {"file_path": file_path, "operation": "get_file_size", "error": "OSError"}})

        # 準備用於結構化日誌的屬性字典
        log_props = {
            "file_path": file_path,
            "file_extension": file_extension,
            "file_size_bytes": file_size, # 可能為 None
            "operation": "extract_text_from_file"
        }

        logger.info(
            f"開始解析檔案 '{file_path}' (類型: {file_extension}, 大小: {file_size} bytes)...",
            extra={"props": {**log_props, "parsing_status": "started"}}
        )

        try:
            # 根據檔案副檔名選擇不同的處理方式
            if file_extension in [".txt", ".md"]:
                # 對於純文字或 Markdown 檔案，直接以 UTF-8 編碼讀取
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                logger.info(
                    f"成功解析純文字檔案: {file_path}",
                    extra={"props": {**log_props, "parsing_status": "success_text_plain", "content_length": len(content)}}
                )
            elif file_extension == ".docx":
                # .docx 檔案的解析功能目前未實現
                content = "[.docx 檔案內容解析功能待實現]" # 返回提示訊息
                logger.warning(
                    f"注意：.docx ({file_path}) 內容解析功能待實現。",
                    extra={"props": {**log_props, "parsing_status": "unsupported_docx"}}
                )
            elif file_extension == ".pdf":
                # .pdf 檔案的解析功能目前未實現
                content = "[.pdf 檔案內容解析功能待實現]" # 返回提示訊息
                logger.warning(
                    f"注意：.pdf ({file_path}) 內容解析功能待實現。",
                    extra={"props": {**log_props, "parsing_status": "unsupported_pdf"}}
                )
            else:
                # 其他所有不支援的檔案類型
                content = f"[不支援的檔案類型: {file_extension}]" # 返回不支援的提示訊息
                logger.warning(
                    f"不支援的檔案類型 '{file_extension}' ({file_path})。",
                    extra={"props": {**log_props, "parsing_status": "unsupported_other", "unsupported_extension": file_extension}}
                )
        except FileNotFoundError:
            # 處理檔案未找到的異常
            content = f"[檔案未找到: {file_path}]" # 設定錯誤訊息
            logger.error(
                f"解析檔案 '{file_path}' 時失敗：檔案未找到。", exc_info=True, # 記錄異常信息
                extra={"props": {**log_props, "parsing_status": "exception_file_not_found", "error": "FileNotFoundError"}}
            )
        except Exception as e:
            # 處理其他所有在解析過程中可能發生的異常
            content = f"[檔案內容解析錯誤: {str(e)}]" # 設定通用錯誤訊息
            logger.error(
                f"解析檔案 '{file_path}' 時發生錯誤: {e}", exc_info=True, # 記錄異常信息
                extra={"props": {**log_props, "parsing_status": "exception_generic", "error": str(e)}}
            )

        return content
