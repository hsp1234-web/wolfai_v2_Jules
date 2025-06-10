# -*- coding: utf-8 -*-
import logging
import time
import asyncio
import json
from typing import Optional, Dict, Any # Added Any

import google.generativeai as genai
from ..config import settings

logger = logging.getLogger(__name__)

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

    def __init__(self):
        """
        初始化 GeminiService。

        在初始化過程中，服務會嘗試從應用程式設定中讀取 Google API 金鑰，
        並使用該金鑰配置 `google.generativeai` 函式庫。
        服務的 `is_configured` 屬性將反映配置是否成功。
        """
        self.is_configured = False
        self.model_name = 'gemini-pro' # 預設使用的 Gemini 模型，未來可以考慮使其可配置。

        logger.info(
            "Gemini AI 服務 (GeminiService) 初始化中...",
            extra={"props": {"service_name": "GeminiService", "initialization_status": "starting"}}
        )

        api_key_secret = settings.COLAB_GOOGLE_API_KEY
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
                        "COLAB_GOOGLE_API_KEY 在設定中存在但為空值，GeminiService 功能將受限。",
                        extra={"props": {"service_name": "GeminiService", "configuration_status": "api_key_empty"}}
                    )
            except Exception as e:
                logger.error(
                    f"配置 Gemini AI API 金鑰時發生錯誤: {e}", exc_info=True,
                    extra={"props": {"service_name": "GeminiService", "configuration_status": "exception", "error": str(e)}}
                )
                # self.is_configured remains False
        else:
            logger.warning(
                "未在設定中找到 COLAB_GOOGLE_API_KEY，GeminiService 功能將受限。",
                extra={"props": {"service_name": "GeminiService", "configuration_status": "api_key_missing"}}
            )

    async def summarize_text(self, text: str, max_retries: int = 1, retry_delay: int = 5) -> Optional[str]:
        """
        使用 Gemini AI 模型對提供的文字內容進行摘要。

        Args:
            text (str): 需要進行摘要的原始文字。
            max_retries (int, optional): API 請求失敗時的最大重試次數。預設為 1。
            retry_delay (int, optional): 每次重試之間的延遲時間 (秒)。預設為 5。

        Returns:
            Optional[str]: 如果成功，返回摘要後的文字字串。
                           如果服務未配置、輸入文字為空、API 請求失敗或回應格式不正確，
                           則返回 None 或包含錯誤訊息的字串。
        """
        operation_props = {"api_action": "summarize_text", "model_name": self.model_name, "input_length": len(text) if text else 0}
        if not self.is_configured:
            logger.warning(
                "GeminiService 未配置 API 金鑰，無法執行摘要。",
                extra={"props": {**operation_props, "error": "service_not_configured"}}
            )
            return "服務未配置或API金鑰無效"

        if not text or not text.strip():
            logger.warning(
                "輸入文字為空，無法進行摘要。",
                extra={"props": {**operation_props, "error": "empty_input_text"}}
            )
            return "輸入文字為空"

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

                if response.parts and response.parts[0].text:
                    summary = response.parts[0].text
                elif hasattr(response, 'text') and response.text:
                    summary = response.text
                else:
                    block_reason = response.prompt_feedback.block_reason if response.prompt_feedback else "Unknown"
                    block_reason_message = response.prompt_feedback.block_reason_message if response.prompt_feedback else "N/A"
                    logger.warning(
                        f"Gemini API 回應中未找到有效的文字內容。阻擋原因: {block_reason}",
                        extra={"props": {**attempt_props, "api_call_status": "no_content", "block_reason": block_reason, "response": str(response)}}
                    )
                    if block_reason != "Unknown": # Check if prompt_feedback exists and has a reason
                         return f"請求因 {block_reason_message} 被阻擋" # Use the message from feedback
                    return "無法從回應中提取摘要"

                logger.info(
                    "成功從 Gemini API 獲取摘要。",
                    extra={"props": {**attempt_props, "api_call_status": "success", "summary_length": len(summary)}}
                )
                return summary
            except Exception as e:
                logger.error(
                    f"Gemini API 文字摘要請求失敗 (嘗試 {attempt + 1}/{max_retries + 1}): {e}", exc_info=True,
                    extra={"props": {**attempt_props, "api_call_status": "exception", "error": str(e)}}
                )
                if attempt < max_retries:
                    logger.info(f"將在 {retry_delay} 秒後重試...", extra={"props": {**attempt_props, "retry_delay_seconds": retry_delay}})
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error("已達到最大重試次數，文字摘要失敗。", extra={"props": {**attempt_props, "final_status": "max_retries_reached"}})
                    return f"API請求錯誤：{str(e)}"

        logger.error("文字摘要請求最終失敗 (迴圈結束)。", extra={"props": {**operation_props, "final_status": "loop_ended_failure"}})
        return "文字摘要請求最終失敗" # 或者可以返回 None，讓呼叫者更一致地處理失敗

    async def analyze_report(self, report_content: str, max_retries: int = 1, retry_delay: int = 5) -> Optional[Dict[str, Any]]:
        """
        使用 Gemini AI 模型對提供的報告內容進行結構化分析。

        該方法會指示模型扮演商業分析師的角色，並要求以 JSON 格式返回分析結果，
        包含 'main_findings', 'potential_risks', 和 'suggested_actions' 三個鍵。

        Args:
            report_content (str): 需要進行分析的報告原文。
            max_retries (int, optional): API 請求失敗時的最大重試次數。預設為 1。
            retry_delay (int, optional): 每次重試之間的延遲時間 (秒)。預設為 5。

        Returns:
            Optional[Dict[str, Any]]: 如果成功，返回一個包含結構化分析結果的字典。
                                      例如：
                                      {
                                          "main_findings": "...",
                                          "potential_risks": "...",
                                          "suggested_actions": "..."
                                      }
                                      如果服務未配置、輸入內容為空、API 請求失敗、回應非預期 JSON 格式
                                      或 JSON 解析失敗，則返回包含 "錯誤" 鍵的字典。
        """
        operation_props = {"api_action": "analyze_report", "model_name": self.model_name, "input_length": len(report_content) if report_content else 0}
        if not self.is_configured:
            logger.warning(
                "GeminiService 未配置 API 金鑰，無法執行報告分析。",
                extra={"props": {**operation_props, "error": "service_not_configured"}}
            )
            return {"錯誤": "服務未配置或API金鑰無效"}

        if not report_content or not report_content.strip():
            logger.warning(
                "報告內容為空，無法進行分析。",
                 extra={"props": {**operation_props, "error": "empty_input_text"}}
            )
            return {"錯誤": "報告內容為空"}

        model = genai.GenerativeModel(self.model_name)
        prompt = (
            "請你扮演一個專業的商業分析師。詳細分析以下報告內容，並嚴格以JSON格式返回一個包含以下三個鍵的中文分析結果："
            "1. 'main_findings' (字串): 總結報告中的主要發現，3-5個重點。"
            "2. 'potential_risks' (字串): 根據報告內容，識別潛在的風險點，2-4個重點。"
            "3. 'suggested_actions' (字串): 基於分析，提出具體的建議行動，2-4個重點。"
            "確保JSON格式正確無誤，所有文字內容都使用中文。"
            "\n\n報告內容：\n---\n"
            f"{report_content}"
            "\n---\n"
            "JSON輸出："
        )
        operation_props["prompt_length"] = len(prompt)

        raw_text_for_error_log = "" # Define in outer scope for logging in case of JSON error

        for attempt in range(max_retries + 1):
            attempt_props = {**operation_props, "attempt": attempt + 1, "max_retries": max_retries}
            try:
                logger.info(
                    f"嘗試向 Gemini API 請求報告分析 (嘗試 {attempt + 1}/{max_retries + 1})...",
                    extra={"props": {**attempt_props, "api_call_status": "started"}}
                )
                response = await model.generate_content_async(prompt)

                if response.parts and response.parts[0].text:
                    raw_text_for_error_log = response.parts[0].text
                elif hasattr(response, 'text') and response.text:
                    raw_text_for_error_log = response.text
                else:
                    block_reason = response.prompt_feedback.block_reason if response.prompt_feedback else "Unknown"
                    block_reason_message = response.prompt_feedback.block_reason_message if response.prompt_feedback else "N/A"
                    logger.warning(
                        f"Gemini API 分析回應中未找到有效的文字內容。阻擋原因: {block_reason}",
                        extra={"props": {**attempt_props, "api_call_status": "no_content", "block_reason": block_reason, "response": str(response)}}
                    )
                    if block_reason != "Unknown":
                         return {"錯誤": f"請求因 {block_reason_message} 被阻擋"}
                    return {"錯誤": "無法從API回應中提取分析文字"}

                logger.debug(f"Gemini API 返回的原始分析文字: {raw_text_for_error_log}", extra={"props": {**attempt_props, "raw_response_text": raw_text_for_error_log}})

                json_text = raw_text_for_error_log
                if "```json" in json_text:
                    json_text = json_text.split("```json")[1].split("```")[0].strip()
                elif "```" in json_text and not json_text.strip().startswith("{"):
                    json_text = json_text.split("```")[1].strip()
                else:
                    json_text = json_text.strip()

                if not json_text.startswith("{") or not json_text.endswith("}"):
                    start_brace = json_text.find("{")
                    end_brace = json_text.rfind("}")
                    if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
                        json_text = json_text[start_brace : end_brace+1]
                    else:
                        raise json.JSONDecodeError("回應內容非預期JSON格式", json_text, 0)

                analysis_result = json.loads(json_text)
                expected_keys = ['main_findings', 'potential_risks', 'suggested_actions']
                if not all(key in analysis_result for key in expected_keys):
                    logger.warning(
                        f"Gemini API 返回的JSON缺少預期鍵值: {analysis_result}",
                        extra={"props": {**attempt_props, "api_call_status": "json_missing_keys", "analysis_result": analysis_result}}
                    )

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
                    logger.info(f"將在 {retry_delay} 秒後重試...", extra={"props": {**attempt_props, "retry_delay_seconds": retry_delay}})
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error("已達到最大重試次數，報告分析JSON解析失敗。", extra={"props": {**attempt_props, "final_status": "max_retries_json_fail"}})
                    return {"錯誤": f"JSON解析錯誤: {str(e_json)}", "原始回應": raw_text_for_error_log}
            except Exception as e:
                logger.error(
                    f"Gemini API 報告分析請求失敗 (嘗試 {attempt + 1}/{max_retries + 1}): {e}", exc_info=True,
                    extra={"props": {**attempt_props, "api_call_status": "exception", "error": str(e)}}
                )
                if attempt < max_retries:
                    logger.info(f"將在 {retry_delay} 秒後重試...", extra={"props": {**attempt_props, "retry_delay_seconds": retry_delay}})
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error("已達到最大重試次數，報告分析失敗。", extra={"props": {**attempt_props, "final_status": "max_retries_api_fail"}})
                    return {"錯誤": f"API請求錯誤: {str(e)}"}

        logger.error("報告分析請求最終失敗 (迴圈結束)。", extra={"props": {**operation_props, "final_status": "loop_ended_failure"}})
        return {"錯誤": "報告分析請求最終失敗"}
