# backend/services/analysis_service.py
import google.generativeai as genai
import os
from typing import List, Dict, Any

# It's assumed that genai.configure(api_key=os.environ["GEMINI_API_KEY"])
# is called once during application startup (e.g., in main.py or a config file).
# Ensure GEMINI_API_KEY is in your environment for this service to work,
# although for tests, this will be mocked.

class AnalysisService:
    def __init__(self):
        # Initialize the model here if it's to be reused across calls,
        # or within the method if model choice depends on params or for simplicity.
        # For now, model is initialized within generate_report.
        # self.model = genai.GenerativeModel('gemini-pro') # Example if pre-initializing
        pass

    def generate_report(self, data_dimensions: List[str]) -> Dict[str, Any]:
        if not data_dimensions:
            return {
                "summary": "綜合分析報告 - AI狼計畫 (無維度)",
                "status": "skipped_ai_call",
                "data_dimensions_received": data_dimensions,
                "details": "未提供分析維度，無法調用 AI 分析。",
                "model_used": None,
                "prompt_sent_to_gemini": None # Ensure all expected keys are present
            }

        try:
            # This check is illustrative. Robust error handling for missing API key
            # configuration should be at a higher level (e.g., app startup).
            # If genai.configure() hasn't been called, the next line will likely fail.
            # This is acceptable as tests will mock GenerativeModel.
            # if not os.getenv("GEMINI_API_KEY") and not genai.API_KEY_NAME in os.environ:
            #     # A more direct way to check if genai library itself has an API key might be needed
            #     # but genai library doesn't expose a simple `is_configured()` check easily.
            #     logger.error("GEMINI_API_KEY not configured for AnalysisService.") # Requires logger setup
            #     raise EnvironmentError("GEMINI_API_KEY is not configured.")


            # It's good practice to use a specific model version for production.
            # Using 'gemini-pro' implies the latest stable 'gemini-pro'.
            # Consider 'gemini-1.5-pro-latest' for newer features if available and tested.
            model = genai.GenerativeModel('gemini-pro')

            # Simulate some structured data based on dimensions for a more realistic prompt
            # In a real scenario, this data would come from DataAccessLayer
            simulated_structured_data = {}
            if "經濟數據" in data_dimensions:
                simulated_structured_data["經濟數據"] = "當前 GDP 成長率為 2.5%，通脹率為 1.8%，失業率為 3.5%。"
            if "市場新聞" in data_dimensions:
                simulated_structured_data["市場新聞"] = "近期科技股表現強勁，特別是 AI 相關產業。然而，傳統能源股面臨壓力。"
            if "地緣政治" in data_dimensions:
                simulated_structured_data["地緣政治"] = "區域衝突導致供應鏈不穩定，黃金價格上漲。"
            # Add a generic dimension if specific ones are not hit, to ensure some data is always present if dimensions are given
            if data_dimensions and not simulated_structured_data:
                 for dim in data_dimensions:
                    if dim not in simulated_structured_data: # Avoid overwriting existing simulated data
                        simulated_structured_data[dim] = f"關於 {dim} 的一般性數據和觀察。"


            prompt_parts = [f"請針對以下提供的數據維度及其相關資訊，生成一份詳細的深度策略分析報告。請著重於各維度間的關聯性、潛在風險與機遇，並提供具體的策略建議。數據維度：{', '.join(data_dimensions)}。\n"]

            if not simulated_structured_data and data_dimensions: # Should be rare now with the generic addition
                prompt_parts.append(f"雖然指定了維度 {', '.join(data_dimensions)}，但目前沒有可用的詳細結構化數據。請基於這些維度名稱進行一般性的策略分析。")
            else:
                for dim, data in simulated_structured_data.items():
                    prompt_parts.append(f"\n維度：{dim}\n相關資訊：{data}\n")

            prompt_parts.append("\n請開始您的分析報告：")
            final_prompt = "".join(prompt_parts)

            # For debugging during development, can be removed or logged in production
            print(f"--- Generated Prompt for Gemini ---")
            print(final_prompt)
            print(f"------------------------------------")

            # Using the synchronous version model.generate_content()
            # If your FastAPI app is heavily async, consider looking into model.generate_content_async()
            # but that requires the calling chain (endpoint and service method) to be async.
            response = model.generate_content(final_prompt)

            analysis_text = ""
            # Robustly extract text content from response.
            # The structure of `response.parts` and `response.text` can vary slightly.
            if response.parts:
                analysis_text = "".join(part.text for part in response.parts if hasattr(part, 'text') and part.text)

            # If no text found in parts, try accessing response.text directly (older versions or simpler responses)
            if not analysis_text and hasattr(response, 'text') and response.text:
                analysis_text = response.text

            # If still no text, it indicates an issue or unexpected response format
            if not analysis_text:
                # Check for error states in response if possible, e.g. prompt feedback
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                    analysis_text = f"無法生成分析報告：Gemini API 因 '{response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}' 拒絕了請求。"
                else:
                    analysis_text = "無法從 Gemini 回應中提取有效的文本內容。回應可能為空或格式不符預期。"


            return {
                "summary": "由 Gemini AI 生成的綜合分析報告",
                "status": "success",
                "data_dimensions_processed": data_dimensions,
                "prompt_sent_to_gemini": final_prompt,
                "analysis_details": analysis_text,
                "model_used": model.model_name # Using model.model_name provides the actual model string like "models/gemini-pro"
            }

        except Exception as e:
            # Basic error logging, replace with your application's standard logger
            print(f"Error calling Gemini API or processing its response: {e}")
            # logger.error(f"Gemini API call failed: {e}", exc_info=True) # Example with a logger

            error_message = str(e)
            # Check for specific GenAI errors if needed, e.g. google.api_core.exceptions.PermissionDenied for API key issues
            # This would require importing `google.api_core.exceptions`.
            # For example:
            # if isinstance(e, google.api_core.exceptions.GoogleAPIError):
            #    error_message = f"Gemini API 錯誤: {e.message}"

            return {
                "summary": "調用 Gemini AI 時發生錯誤",
                "status": "error_calling_ai",
                "data_dimensions_processed": data_dimensions,
                "prompt_sent_to_gemini": final_prompt if 'final_prompt' in locals() else "提示詞生成階段發生錯誤", # Include prompt if available
                "error_message": error_message,
                "model_used": 'gemini-pro' # Model name might not be available from `model` object if initialization failed
            }
