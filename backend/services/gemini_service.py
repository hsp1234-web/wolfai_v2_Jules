# -*- coding: utf-8 -*-
import logging
import time
import asyncio
import json
from typing import Optional, Dict, Any

import google.generativeai as genai
from google.generativeai.types import generation_types # For error handling if needed

from ..config import settings

logger = logging.getLogger(__name__)

# Custom Exceptions
class GeminiServiceError(Exception):
    """Base exception for GeminiService issues."""
    pass

class GeminiNotConfiguredError(GeminiServiceError):
    """Raised when the service is not configured (e.g., API key missing)."""
    pass

class GeminiAPIError(GeminiServiceError):
    """Raised for errors returned by the Gemini API itself."""
    def __init__(self, message, original_exception=None):
        super().__init__(message)
        self.original_exception = original_exception

class GeminiJSONParsingError(GeminiServiceError):
    """Raised when JSON parsing of API response fails."""
    def __init__(self, message, raw_text=None):
        super().__init__(message)
        self.raw_text = raw_text

class GeminiBlockedPromptError(GeminiServiceError):
    """Raised when the prompt is blocked by the API."""
    def __init__(self, message, block_reason=None, block_reason_message=None):
        super().__init__(message)
        self.block_reason = block_reason
        self.block_reason_message = block_reason_message

class GeminiEmptyResponseError(GeminiServiceError):
    """Raised when the API returns an empty or unexpected response."""
    pass


class GeminiService:
    """
    提供使用 Google Gemini AI 模型進行文字摘要和結構化分析的服務。

    該服務封裝了與 Google Gemini API 互動的邏輯，包括：
    - API 金鑰的配置與管理。
    - 呼叫 Gemini 模型進行文字摘要。
    - 呼叫 Gemini 模型進行特定結構的報告分析 (例如，提取主要發現、潛在風險、建議行動)。
    - 處理 API 請求的重試機制。
    - 解析和記錄 API 的回應。
    """

    def __init__(self, model_name: str = 'gemini-pro'):
        """
        初始化 GeminiService。

        Args:
            model_name (str): 要使用的 Gemini 模型的名稱。

        在初始化過程中，服務會嘗試從應用程式設定中讀取 Google API 金鑰，
        並使用該金鑰配置 `google.generativeai` 函式庫。
        服務的 `is_configured` 屬性將反映配置是否成功。
        """
        self.model_name = model_name
        self.is_configured = False

        logger.info(
            f"Gemini AI 服務 (GeminiService) 初始化中 (模型: {self.model_name})...",
            extra={"props": {"service_name": "GeminiService", "model_name": self.model_name, "initialization_status": "starting"}}
        )

        api_key_secret = settings.GOOGLE_API_KEY
        if api_key_secret:
            try:
                api_key = api_key_secret.get_secret_value()
                if api_key:
                    genai.configure(api_key=api_key)
                    self.is_configured = True
                    logger.info(
                        "Gemini AI (genai) 已成功配置 API 金鑰。",
                        extra={"props": {"service_name": "GeminiService", "configuration_status": "success"}}
                    )
                else:
                    logger.warning(
                        "GOOGLE_API_KEY 在設定中存在但為空值，GeminiService 功能將受限。",
                        extra={"props": {"service_name": "GeminiService", "configuration_status": "api_key_empty"}}
                    )
                    # No need to raise GeminiNotConfiguredError here, methods will check self.is_configured
            except Exception as e:
                logger.error(
                    f"配置 Gemini AI API 金鑰時發生錯誤: {e}", exc_info=True,
                    extra={"props": {"service_name": "GeminiService", "configuration_status": "exception", "error": str(e)}}
                )
                # self.is_configured remains False
        else:
            logger.warning(
                "未在設定中找到 GOOGLE_API_KEY，GeminiService 功能將受限。",
                extra={"props": {"service_name": "GeminiService", "configuration_status": "api_key_missing"}}
            )
            # No need to raise GeminiNotConfiguredError here, methods will check self.is_configured

    async def summarize_text(self, text: str, max_retries: int = 1, retry_delay: int = 5) -> str:
        """
        使用 Gemini AI 模型對提供的文字內容進行摘要。

        Args:
            text (str): 需要進行摘要的原始文字。
            max_retries (int, optional): API 請求失敗時的最大重試次數。預設為 1。
            retry_delay (int, optional): 每次重試之間的延遲時間 (秒)。預設為 5。

        Returns:
            str: 摘要後的文字字串。

        Raises:
            GeminiNotConfiguredError: 如果服務未配置 API 金鑰。
            ValueError: 如果輸入文字為空。
            GeminiBlockedPromptError: 如果提示被 API 阻擋。
            GeminiEmptyResponseError: 如果 API 回應為空或不符合預期。
            GeminiAPIError: 如果 API 請求失敗。
        """
        operation_props = {"api_action": "summarize_text", "model_name": self.model_name, "input_length": len(text) if text else 0}
        if not self.is_configured:
            logger.warning("GeminiService 未配置 API 金鑰，無法執行摘要。", extra={"props": {**operation_props, "error_type": "GeminiNotConfiguredError"}})
            raise GeminiNotConfiguredError("GeminiService is not configured with an API key.")

        if not text or not text.strip():
            logger.warning("輸入文字為空，無法進行摘要。", extra={"props": {**operation_props, "error_type": "ValueError"}})
            raise ValueError("Input text cannot be empty.")

        model = genai.GenerativeModel(self.model_name)
        prompt = f"請將以下文字內容進行摘要，並以中文輸出重點：\n\n---\n{text}\n---"
        operation_props["prompt_length"] = len(prompt)

        for attempt in range(max_retries + 1):
            attempt_props = {**operation_props, "attempt": attempt + 1, "max_retries": max_retries}
            try:
                logger.info(
                    f"嘗試向 Gemini API 請求文字摘要 (嘗試 {attempt + 1}/{max_retries + 1})...",
                    extra={"props": {**attempt_props, "api_call_status": "started"}}
                )
                response = await model.generate_content_async(prompt)

                summary = ""
                if response.parts:
                    summary = "".join(part.text for part in response.parts if hasattr(part, 'text') and part.text)
                elif hasattr(response, 'text') and response.text: # Fallback for simpler responses
                    summary = response.text

                if not summary: # Check if summary is still empty
                    if response.prompt_feedback and response.prompt_feedback.block_reason:
                        logger.warning(
                            f"Gemini API 請求被阻擋。原因: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}",
                            extra={"props": {**attempt_props, "api_call_status": "blocked", "block_reason": response.prompt_feedback.block_reason, "response": str(response)}}
                        )
                        raise GeminiBlockedPromptError(
                            f"Prompt was blocked: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}",
                            block_reason=response.prompt_feedback.block_reason,
                            block_reason_message=response.prompt_feedback.block_reason_message
                        )
                    else:
                        logger.warning(
                            "Gemini API 回應中未找到有效的文字內容。",
                            extra={"props": {**attempt_props, "api_call_status": "no_content", "response": str(response)}}
                        )
                        raise GeminiEmptyResponseError("Gemini API returned an empty or unexpected response.")

                logger.info(
                    "成功從 Gemini API 獲取摘要。",
                    extra={"props": {**attempt_props, "api_call_status": "success", "summary_length": len(summary)}}
                )
                return summary
            except (GeminiBlockedPromptError, GeminiEmptyResponseError) as e_gemini_known: # Re-raise known errors
                if attempt < max_retries:
                    logger.info(f"將在 {retry_delay} 秒後重試 ({type(e_gemini_known).__name__})...", extra={"props": {**attempt_props, "retry_delay_seconds": retry_delay}})
                    await asyncio.sleep(retry_delay)
                else:
                    raise # Raise the caught exception if max_retries reached
            except Exception as e:
                logger.error(
                    f"Gemini API 文字摘要請求失敗 (嘗試 {attempt + 1}/{max_retries + 1}): {e}", exc_info=True,
                    extra={"props": {**attempt_props, "api_call_status": "exception", "error_type": type(e).__name__, "error": str(e)}}
                )
                if attempt < max_retries:
                    logger.info(f"將在 {retry_delay} 秒後重試...", extra={"props": {**attempt_props, "retry_delay_seconds": retry_delay}})
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error("已達到最大重試次數，文字摘要失敗。", extra={"props": {**attempt_props, "final_status": "max_retries_reached"}})
                    raise GeminiAPIError(f"Gemini API request failed after {max_retries + 1} attempts: {str(e)}", original_exception=e)

        # This part should ideally not be reached if logic is correct (either returns summary or raises error)
        logger.error("文字摘要請求最終失敗 (迴圈結束異常)。", extra={"props": {**operation_props, "final_status": "loop_ended_failure_unexpected"}})
        raise GeminiServiceError("Text summarization failed after all retries.")


    async def analyze_report(self, prompt_text: str, max_retries: int = 1, retry_delay: int = 5) -> Dict[str, Any]:
        """
        使用 Gemini AI 模型對提供的完整提示文字進行分析，並期望返回 JSON。

        Args:
            prompt_text (str): 包含完整指令和內容的提示文字，期望模型返回 JSON。
            max_retries (int, optional): API 請求失敗時的最大重試次數。預設為 1。
            retry_delay (int, optional): 每次重試之間的延遲時間 (秒)。預設為 5。

        Returns:
            Dict[str, Any]: 包含結構化分析結果的字典。

        Raises:
            GeminiNotConfiguredError: 如果服務未配置 API 金鑰。
            ValueError: 如果輸入提示文字為空。
            GeminiBlockedPromptError: 如果提示被 API 阻擋。
            GeminiEmptyResponseError: 如果 API 回應為空或不符合預期。
            GeminiJSONParsingError: 如果 API 回應無法解析為 JSON。
            GeminiAPIError: 如果 API 請求失敗。
        """
        operation_props = {"api_action": "analyze_report", "model_name": self.model_name, "input_length": len(prompt_text) if prompt_text else 0}
        if not self.is_configured:
            logger.warning("GeminiService 未配置 API 金鑰，無法執行報告分析。", extra={"props": {**operation_props, "error_type": "GeminiNotConfiguredError"}})
            raise GeminiNotConfiguredError("GeminiService is not configured with an API key.")

        if not prompt_text or not prompt_text.strip():
            logger.warning("輸入提示文字為空，無法進行分析。", extra={"props": {**operation_props, "error_type": "ValueError"}})
            raise ValueError("Input prompt text cannot be empty.")

        model = genai.GenerativeModel(self.model_name)
        # The prompt_text is now the full prompt, no internal construction needed.
        operation_props["prompt_length"] = len(prompt_text)

        raw_text_for_error_log = ""

        for attempt in range(max_retries + 1):
            attempt_props = {**operation_props, "attempt": attempt + 1, "max_retries": max_retries}
            try:
                logger.info(
                    f"嘗試向 Gemini API 請求報告分析 (嘗試 {attempt + 1}/{max_retries + 1})...",
                    extra={"props": {**attempt_props, "api_call_status": "started"}}
                )
                response = await model.generate_content_async(prompt_text) # Use prompt_text directly

                raw_text_for_error_log = "" # Reset for each attempt
                if response.parts:
                    raw_text_for_error_log = "".join(part.text for part in response.parts if hasattr(part, 'text') and part.text)
                elif hasattr(response, 'text') and response.text:
                    raw_text_for_error_log = response.text

                if not raw_text_for_error_log:
                    if response.prompt_feedback and response.prompt_feedback.block_reason:
                        logger.warning(
                            f"Gemini API 請求被阻擋。原因: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}",
                            extra={"props": {**attempt_props, "api_call_status": "blocked", "block_reason": response.prompt_feedback.block_reason, "response": str(response)}}
                        )
                        raise GeminiBlockedPromptError(
                            f"Prompt was blocked: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}",
                            block_reason=response.prompt_feedback.block_reason,
                            block_reason_message=response.prompt_feedback.block_reason_message
                        )
                    else:
                        logger.warning(
                            "Gemini API 分析回應中未找到有效的文字內容。",
                            extra={"props": {**attempt_props, "api_call_status": "no_content", "response": str(response)}}
                        )
                        raise GeminiEmptyResponseError("Gemini API returned an empty or unexpected response for analysis.")

                logger.debug(f"Gemini API 返回的原始分析文字: {raw_text_for_error_log}", extra={"props": {**attempt_props, "raw_response_text": raw_text_for_error_log}})

                json_text = raw_text_for_error_log
                # Basic extraction of JSON from markdown code blocks if present
                if "```json" in json_text:
                    json_text = json_text.split("```json")[1].split("```")[0].strip()
                elif "```" in json_text and not json_text.strip().startswith("{"): # Handle if only ``` not ```json
                    json_text = json_text.split("```")[1].strip()
                else: # Assume it's plain JSON or needs cleaning
                    json_text = json_text.strip()

                # Further ensure it's a valid JSON object (starts with { ends with })
                if not json_text.startswith("{") or not json_text.endswith("}"):
                    start_brace = json_text.find("{")
                    end_brace = json_text.rfind("}")
                    if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
                        json_text = json_text[start_brace : end_brace+1]
                    else: # If still not a valid structure, parsing will fail, caught by JSONDecodeError
                        logger.warning(f"Response content does not appear to be a JSON object: {json_text[:100]}...", extra={"props": {**attempt_props, "json_cleaning_issue": True}})


                analysis_result = json.loads(json_text)
                # Optional: Basic validation if specific keys are always expected (AnalysisService might do this too)
                # expected_keys = ['main_findings', 'potential_risks', 'suggested_actions']
                # if not all(key in analysis_result for key in expected_keys):
                #     logger.warning(
                #         f"Gemini API 返回的JSON缺少預期鍵值: {analysis_result}",
                #         extra={"props": {**attempt_props, "api_call_status": "json_missing_keys", "analysis_result": analysis_result}}
                #     )

                logger.info(
                    "成功從 Gemini API 獲取並解析報告分析結果。",
                    extra={"props": {**attempt_props, "api_call_status": "success"}}
                )
                return analysis_result
            except json.JSONDecodeError as e_json:
                logger.error(
                    f"解析 Gemini API 的報告分析回應為 JSON 時失敗 (嘗試 {attempt + 1}/{max_retries + 1}): {e_json}", exc_info=True,
                    extra={"props": {**attempt_props, "api_call_status": "json_decode_error", "error": str(e_json), "raw_response_text": raw_text_for_error_log}}
                )
                if attempt < max_retries:
                    logger.info(f"將在 {retry_delay} 秒後重試 (JSON解析錯誤)...", extra={"props": {**attempt_props, "retry_delay_seconds": retry_delay}})
                    await asyncio.sleep(retry_delay)
                else:
                    raise GeminiJSONParsingError(f"Failed to parse Gemini API response as JSON after {max_retries + 1} attempts: {e_json}", raw_text=raw_text_for_error_log)
            except (GeminiBlockedPromptError, GeminiEmptyResponseError) as e_gemini_known: # Re-raise known errors
                if attempt < max_retries:
                    logger.info(f"將在 {retry_delay} 秒後重試 ({type(e_gemini_known).__name__})...", extra={"props": {**attempt_props, "retry_delay_seconds": retry_delay}})
                    await asyncio.sleep(retry_delay)
                else:
                    raise
            except Exception as e:
                logger.error(
                    f"Gemini API 報告分析請求失敗 (嘗試 {attempt + 1}/{max_retries + 1}): {e}", exc_info=True,
                    extra={"props": {**attempt_props, "api_call_status": "exception", "error_type": type(e).__name__, "error": str(e)}}
                )
                if attempt < max_retries:
                    logger.info(f"將在 {retry_delay} 秒後重試...", extra={"props": {**attempt_props, "retry_delay_seconds": retry_delay}})
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error("已達到最大重試次數，報告分析失敗。", extra={"props": {**attempt_props, "final_status": "max_retries_api_fail"}})
                    raise GeminiAPIError(f"Gemini API request for analysis failed after {max_retries + 1} attempts: {str(e)}", original_exception=e)

        logger.error("報告分析請求最終失敗 (迴圈結束異常)。", extra={"props": {**operation_props, "final_status": "loop_ended_failure_unexpected"}})
        raise GeminiServiceError("Report analysis failed after all retries.")
