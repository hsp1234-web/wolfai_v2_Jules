# -*- coding: utf-8 -*-
import os
import logging

logger = logging.getLogger(__name__)

class ParsingService:
    """
    提供從不同檔案類型中提取文字內容的服務。
    """

    def __init__(self):
        """
        初始化文字解析服務。
        """
        logger.info(
            "文字解析服務 (ParsingService) 已初始化。",
            extra={"props": {"service_name": "ParsingService", "status": "initialized"}}
        )

    def _get_file_extension(self, file_name: str) -> str:
        """
        獲取檔案的小寫副檔名。
        """
        return os.path.splitext(file_name)[1].lower()

    def extract_text_from_file(self, file_path: str) -> str:
        """
        從指定的本地檔案路徑提取文字內容。
        """
        file_extension = self._get_file_extension(file_path)
        content = ""
        # Determine file size for context, handle potential errors if file_path is invalid early
        file_size = None
        try:
            if os.path.exists(file_path): # Check existence before getting size
                file_size = os.path.getsize(file_path)
        except OSError: # Catch errors from os.path.exists or os.path.getsize
             logger.warning(f"無法獲取檔案大小或檢查檔案是否存在: {file_path}", extra={"props": {"file_path": file_path, "operation": "get_file_size", "error": "OSError"}})


        log_props = {
            "file_path": file_path,
            "file_extension": file_extension,
            "file_size_bytes": file_size,
            "operation": "extract_text_from_file"
        }

        logger.info(
            f"開始解析檔案 '{file_path}' (類型: {file_extension}, 大小: {file_size} bytes)...",
            extra={"props": {**log_props, "parsing_status": "started"}}
        )

        try:
            if file_extension in [".txt", ".md"]:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                logger.info(
                    f"成功解析純文字檔案: {file_path}",
                    extra={"props": {**log_props, "parsing_status": "success_text_plain", "content_length": len(content)}}
                )
            elif file_extension == ".docx":
                content = "[.docx 檔案內容解析功能待實現]"
                logger.warning(
                    f"注意：.docx ({file_path}) 內容解析功能待實現。",
                    extra={"props": {**log_props, "parsing_status": "unsupported_docx"}}
                )
            elif file_extension == ".pdf":
                content = "[.pdf 檔案內容解析功能待實現]"
                logger.warning(
                    f"注意：.pdf ({file_path}) 內容解析功能待實現。",
                    extra={"props": {**log_props, "parsing_status": "unsupported_pdf"}}
                )
            else:
                content = f"[不支援的檔案類型: {file_extension}]"
                logger.warning(
                    f"不支援的檔案類型 '{file_extension}' ({file_path})。",
                    extra={"props": {**log_props, "parsing_status": "unsupported_other", "unsupported_extension": file_extension}}
                )
        except FileNotFoundError:
            content = f"[檔案未找到: {file_path}]"
            logger.error(
                f"解析檔案 '{file_path}' 時失敗：檔案未找到。", exc_info=True, # exc_info might be redundant if FileNotFoundError is caught explicitly
                extra={"props": {**log_props, "parsing_status": "exception_file_not_found", "error": "FileNotFoundError"}}
            )
        except Exception as e:
            content = f"[檔案內容解析錯誤: {str(e)}]"
            logger.error(
                f"解析檔案 '{file_path}' 時發生錯誤: {e}", exc_info=True,
                extra={"props": {**log_props, "parsing_status": "exception_generic", "error": str(e)}}
            )

        return content
