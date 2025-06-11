# backend/services/analysis_service.py
import logging
from typing import List, Dict, Any
from .gemini_service import GeminiService, GeminiServiceError # Import the correct exception

# Placeholder for GeminiService specific errors
# class GeminiServiceError(Exception): # REMOVE THIS PLACEHOLDER
#     pass                           # REMOVE THIS PLACEHOLDER

class AnalysisService:
    def __init__(self, gemini_service: GeminiService):
        self.gemini_service = gemini_service
        self.logger = logging.getLogger(__name__)

    async def generate_report(self, data_dimensions: List[str]) -> Dict[str, Any]:
        self.logger.info(
            "Generating analysis report for dimensions: %s",
            data_dimensions,
            extra={
                "props": {
                    "service": "AnalysisService",
                    "event": "report_generation_start",
                    "data_dimensions": data_dimensions,
                }
            },
        )

        if not data_dimensions:
            self.logger.warning(
                "Data dimensions are empty. Skipping AI call.",
                extra={
                    "props": {
                        "service": "AnalysisService",
                        "event": "report_generation_skipped",
                        "reason": "empty_data_dimensions",
                    }
                },
            )
            return {
                "summary": "綜合分析報告 - AI狼計畫 (無維度)",
                "status": "skipped_ai_call",
                "data_dimensions_processed": data_dimensions,
                "analysis_details": "未提供分析維度，無法調用 AI 分析。",
                "model_used": None
            }

        prompt = (
            f"請針對以下數據維度，生成一份詳細的深度策略分析報告。"
            f"請著重於各維度間的關聯性、潛在風險與機遇，並提供具體的策略建議。"
            f"數據維度：{', '.join(data_dimensions)}。\n"
            f"請以JSON格式返回分析結果，包含三個鍵: 'main_findings' (字串), 'potential_risks' (字串), 'suggested_actions' (字串)。"
            f"所有文字內容都使用中文。"
        )

        try:
            analysis_result = await self.gemini_service.analyze_report(report_content=prompt)

            if isinstance(analysis_result, dict):
                self.logger.info(
                    "Successfully generated analysis report.",
                    extra={"props": {"service": "AnalysisService", "event": "report_generation_success"}},
                )
                return {
                    "summary": "由 AI 生成的綜合分析報告",
                    "status": "success",
                    "data_dimensions_processed": data_dimensions,
                    "analysis_details": analysis_result,
                    "model_used": self.gemini_service.model_name
                }
            else:
                # This case handles if gemini_service.analyze_report doesn't return a dict as expected
                # but also doesn't raise an exception.
                self.logger.error(
                    "GeminiService returned an unexpected result type: %s",
                    type(analysis_result),
                    extra={
                        "props": {
                            "service": "AnalysisService",
                            "event": "report_generation_failure",
                            "reason": "unexpected_gemini_result_type",
                            "data_dimensions": data_dimensions,
                        }
                    },
                )
                return {
                    "summary": "AI服務返回結果格式不符預期",
                    "status": "error_ai_response_format",
                    "data_dimensions_processed": data_dimensions,
                    "error_message": f"Expected a dictionary from GeminiService, but got {type(analysis_result)}.",
                    "model_used": self.gemini_service.model_name
                }

        except GeminiServiceError as e:
            # self.logger.debug(f"Caught GeminiServiceError: {type(e)}, issubclass: {issubclass(type(e), GeminiServiceError)}") # Remove debug
            self.logger.error(
                "Error generating analysis report from GeminiService: %s",
                e,
                exc_info=True,
                extra={
                    "props": {
                        "service": "AnalysisService",
                        "event": "report_generation_failure",
                        "data_dimensions": data_dimensions,
                    }
                },
            )
            return {
                "summary": "調用 AI 服務時發生錯誤",
                "status": "error_calling_ai",
                "data_dimensions_processed": data_dimensions,
                "error_message": str(e),
                "model_used": self.gemini_service.model_name if hasattr(self.gemini_service, 'model_name') else None
            }
        except Exception as e: # Catch any other unexpected errors
            # self.logger.debug(f"Caught generic Exception: {type(e)}, issubclass GeminiServiceError: {issubclass(type(e), GeminiServiceError) if GeminiServiceError else 'GeminiServiceError_not_defined_here'}") # Remove debug
            self.logger.error(
                "An unexpected error occurred during report generation: %s",
                e,
                exc_info=True,
                extra={
                    "props": {
                        "service": "AnalysisService",
                        "event": "report_generation_failure",
                        "reason": "unexpected_error",
                        "data_dimensions": data_dimensions,
                    }
                },
            )
            return {
                "summary": "生成報告時發生未知錯誤",
                "status": "error_unknown",
                "data_dimensions_processed": data_dimensions,
                "error_message": str(e),
                "model_used": self.gemini_service.model_name if hasattr(self.gemini_service, 'model_name') else None
            }
