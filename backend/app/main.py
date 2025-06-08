import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any
from . import prompt_service # Added import
from . import ai_service    # Added import
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    os.environ['TZ'] = 'Asia/Taipei'
    if hasattr(time, 'tzset'):
        time.tzset()
    logger.info(f"時區已嘗試設定為 Asia/Taipei。目前時間: {time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
except Exception as e:
    logger.warning(f"設定時區時發生錯誤: {e}")

app = FastAPI(
    title="善甲狼週報 V2.0 API",
    version="1.0.0",
    description="用於善甲狼週報可觀測性分析平台的後端 API"
)

DATA_STORAGE_PATH = "data_storage/shan_jia_lang_posts/"
LOGS_DIR = "logs"

os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(DATA_STORAGE_PATH, exist_ok=True)

class ChatRequest(BaseModel):
    report_content: str = Field(..., description="當前選擇的週報完整內容。")
    api_key: str = Field(..., description="使用者的 Google Gemini API 金鑰。")
    selected_model: str = Field(..., description="使用者選擇的 Gemini 模型名稱。")
    chat_history: List[Dict[str, str]] = Field(default_factory=list, description="過去的對話歷史，格式為 [{'role': 'user'/'model', 'content': '...'}, ...]。")
    user_question: str = Field(..., description="使用者提出的最新問題。")

class ReportListResponse(BaseModel):
    files: List[str] = Field(..., description="週報 .txt 檔案的列表。")

class ErrorResponse(BaseModel):
    detail: str = Field(..., description="錯誤的詳細信息。")

class ChatResponse(BaseModel):
    reply: str = Field(..., description="AI 模型生成的回覆。")

class FrontendLogReceipt(BaseModel):
    status: str = Field("前端日誌已接收", description="確認前端日誌已被接收的狀態。")

class HealthCheckResponse(BaseModel):
    status: str = Field("ok", description="服務狀態。")
    timestamp_tw: str = Field(..., description="當前伺服器時間 (台灣時區)。")
    api_version: str = Field(app.version, description="API 版本。")

@app.get(
    "/api/reports",
    response_model=ReportListResponse,
    summary="獲取週報檔案列表",
    description=f"{DATA_STORAGE_PATH} 目錄下所有 .txt 檔案的檔名列表。"
)
async def get_reports_list():
    try:
        if not os.path.isdir(DATA_STORAGE_PATH):
            logger.error(f"錯誤: 週報儲存路徑 {DATA_STORAGE_PATH} 不是一個有效的資料夾。")
            os.makedirs(DATA_STORAGE_PATH, exist_ok=True)
            return ReportListResponse(files=[])

        files = [f for f in os.listdir(DATA_STORAGE_PATH) if f.endswith(".txt") and os.path.isfile(os.path.join(DATA_STORAGE_PATH, f))]
        logger.info(f"成功獲取週報列表，共 {len(files)} 個檔案。")
        return ReportListResponse(files=sorted(files))
    except Exception as e:
        logger.exception(f"讀取週報列表時發生嚴重錯誤: {e}")
        raise HTTPException(status_code=500, detail="伺服器內部錯誤，無法讀取週報列表。")

@app.get(
    "/api/reports/{filename:path}",
    response_class=PlainTextResponse,
    summary="獲取單篇週報內容",
    description="根據檔名返回單篇週報的完整文字內容。",
    responses={
        200: {"content": {"text/plain": {"example": "這是週報的內容..."}}},
        400: {"model": ErrorResponse, "description": "無效的檔案名稱或格式。"},
        404: {"model": ErrorResponse, "description": "檔案未找到。"},
        500: {"model": ErrorResponse, "description": "伺服器內部錯誤。"}
    }
)
async def get_report_content(filename: str):
    logger.info(f"get_report_content called with filename: '{filename}'")
    if not filename.endswith(".txt") or "/" in filename or "\\\\" in filename or ".." in filename:
        logger.warning(f"無效的檔案名稱請求 (Check 1 triggered for '{filename}')")
        raise HTTPException(status_code=400, detail="無效的檔案名稱或格式。")

    try:
        filepath = os.path.join(DATA_STORAGE_PATH, filename)
        if not os.path.abspath(filepath).startswith(os.path.abspath(DATA_STORAGE_PATH)):
            logger.error(f"潛在的路徑遍歷嘗試被阻止 (Check 2 triggered for '{filename}', filepath '{filepath}')")
            raise HTTPException(status_code=400, detail="禁止存取無效路徑。")

        if os.path.isfile(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.info(f"成功讀取檔案: {filename}")
            return PlainTextResponse(content=content)
        else:
            logger.warning(f"請求的檔案未找到: {filename} (路徑: {filepath})\")")
            raise HTTPException(status_code=404, detail="檔案未找到。")
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.exception(f"讀取檔案 {filename} 時發生嚴重錯誤: {e}")
        raise HTTPException(status_code=500, detail=f"伺服器內部錯誤，無法讀取檔案 {filename}。")

@app.post(
    "/api/chat",
    response_model=ChatResponse,
    summary="核心聊天接口",
    description="接收使用者問題、週報內容、API 金鑰、模型選擇和聊天歷史，返回 AI 生成的回覆。"
)
async def chat_with_report(request: ChatRequest):
    logger.info(f"收到聊天請求。模型: {request.selected_model}, API 金鑰 (前5碼): {request.api_key[:5]}...")
    logger.debug(f"聊天請求詳細內容: 週報字數={len(request.report_content)}, 歷史={len(request.chat_history)}, 問題='{request.user_question}'")

    # 1. 使用 prompt_service 建構提示詞
    try:
        current_prompt = prompt_service.build_contextual_qa_prompt(
            report_content=request.report_content,
            chat_history=request.chat_history,
            user_question=request.user_question
        )
        logger.debug(f"建構的提示詞 (前100字): {current_prompt[:100]}...")
    except Exception as e:
        logger.exception("建構提示詞時發生錯誤")
        raise HTTPException(status_code=500, detail="建構提示詞失敗")

    # 2. 使用 ai_service 獲取 AI 回覆 (目前是 mock)
    try:
        ai_response = await ai_service.get_ai_reply(
            prompt=current_prompt,
            api_key=request.api_key,
            selected_model=request.selected_model
        )
        logger.info(f"從 ai_service (mock) 收到回覆: {ai_response}")
    except Exception as e:
        logger.exception("調用 AI 服務時發生錯誤")
        raise HTTPException(status_code=500, detail="AI 服務調用失敗")

    # 假設 ai_response 是一個包含 'reply' 鍵的字典
    return ChatResponse(reply=ai_response.get("reply", "抱歉，發生了未知錯誤。"))

@app.post(
    "/api/logs/frontend",
    response_model=FrontendLogReceipt,
    summary="接收前端日誌",
    description="用於前端將重要日誌事件發送到後端進行統一記錄。"
)
async def receive_frontend_log(log_data: Dict[str, Any]):
    logger.info(f"收到前端日誌: {log_data}")
    return FrontendLogReceipt()

@app.get(
    "/api/health",
    response_model=HealthCheckResponse,
    summary="健康檢查端點",
    description="提供服務的健康狀態、當前時間（台灣時區）和 API 版本。"
)
async def health_check():
    current_time_tw = "獲取時間失敗"
    try:
        current_time_tw = time.strftime('%Y-%m-%d %H:%M:%S %Z')
    except Exception as e:
        logger.error(f"健康檢查中獲取台灣時間失敗: {e}")
    logger.info(f"健康檢查請求，狀態: ok, 時間: {current_time_tw}")
    return HealthCheckResponse(timestamp_tw=current_time_tw)

if __name__ == "__main__":
    logger.info("FastAPI 應用程式 (main.py) 被直接執行。")
    print("正在啟動 Uvicorn 伺服器 (用於本地開發)...")
    print("請在瀏覽器中打開 http://localhost:8000/docs 查看 API 文件。")
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
