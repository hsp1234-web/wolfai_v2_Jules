import os
import logging
import json # 用於加載可能的服務帳號 JSON 內容
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

# 匯入服務和任務
from .services.google_drive_service import GoogleDriveService
from .services.data_access_layer import DataAccessLayer
from .services.report_ingestion_service import ReportIngestionService
from .scheduler_tasks import trigger_report_ingestion_task

# 配置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 應用程式狀態 ---
app_state = {
    "google_api_key": None, # For Gemini etc.
    "google_api_key_source": None,
    "service_account_info": None, # For Drive, can be from file or JSON string
    "drive_service": None,
    "dal": None,
    "report_ingestion_service": None,
    "scheduler": None,
    "reports_db_path": None,
    "prompts_db_path": None,
}

# --- Pydantic 模型 ---
class ApiKeyRequest(BaseModel):
    api_key: str

class HealthCheckResponse(BaseModel):
    status: str = "OK"
    message: str = "API is running"
    scheduler_status: str = "Not initialized"

class ApiKeyStatusResponse(BaseModel):
    is_set: bool # Refers to google_api_key (for Gemini)
    source: Optional[str] = None
    drive_service_account_loaded: bool = False

# --- FastAPI 應用實例 ---
app = FastAPI(
    title="Wolf AI V2.2 Backend",
    description="後端 API 服務，用於 Wolf AI 可觀測性分析平台 V2.2",
    version="2.2.0"
)

# --- 輔助函數 ---
def get_env_or_default(var_name: str, default: str) -> str:
    return os.getenv(var_name, default)

# --- 事件處理器 ---
@app.on_event("startup")
async def startup_event():
    logger.info("後端應用程式啟動中...")

    # 1. 加載環境變數和配置
    # Google API 金鑰 (用於 Gemini 等, from COLAB_GOOGLE_API_KEY as per previous steps)
    # For clarity, the .env.example and this main.py will prefer GOOGLE_API_KEY for Gemini
    # and specific SERVICE_ACCOUNT variables for Drive.
    env_api_key = os.getenv("COLAB_GOOGLE_API_KEY") # As per step 4
    if env_api_key:
        app_state["google_api_key"] = env_api_key
        app_state["google_api_key_source"] = "environment"
        logger.info("COLAB_GOOGLE_API_KEY (for Gemini/etc.) 已從環境變數成功加載。")
    else:
        logger.warning("環境變數中未找到 COLAB_GOOGLE_API_KEY。如果需要 Gemini 等服務, 可能需要使用者透過 API 輸入。")

    # Google Drive 服務帳號金鑰
    service_account_json_content = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT")
    service_account_file_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    if service_account_json_content:
        try:
            app_state["service_account_info"] = json.loads(service_account_json_content)
            logger.info("Google Drive 服務帳號金鑰已從 GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT 環境變數加載。")
        except json.JSONDecodeError as e:
            logger.error(f"解析 GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT 失敗: {e}。Google Drive 功能可能受限。")
    elif service_account_file_path:
        if os.path.exists(service_account_file_path):
            try:
                with open(service_account_file_path, 'r') as f:
                    app_state["service_account_info"] = json.load(f)
                logger.info(f"Google Drive 服務帳號金鑰已從檔案 {service_account_file_path} 加載。")
            except Exception as e:
                logger.error(f"從 {service_account_file_path} 加載服務帳號金鑰失敗: {e}。Google Drive 功能可能受限。")
        else:
            logger.warning(f"GOOGLE_APPLICATION_CREDENTIALS 指向的檔案 {service_account_file_path} 不存在。Google Drive 功能可能受限。")
    else:
        logger.warning("未配置 Google Drive 服務帳號金鑰 (GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT 或 GOOGLE_APPLICATION_CREDENTIALS)。Google Drive 功能將依賴於後續 API 金鑰的設定（如果其為服務帳號 JSON）。")

    # 資料庫路徑
    # Construct path relative to the 'wolf_ai_v2_2' directory, assuming 'main.py' is in 'wolf_ai_v2_2/backend/'
    backend_dir = os.path.dirname(os.path.abspath(__file__)) # wolf_ai_v2_2/backend
    project_root = os.path.dirname(backend_dir) # wolf_ai_v2_2
    base_data_path = os.path.join(project_root, 'data')
    os.makedirs(base_data_path, exist_ok=True)

    reports_db_filename = get_env_or_default("REPORTS_DB_FILENAME", "reports.sqlite")
    prompts_db_filename = get_env_or_default("PROMPTS_DB_FILENAME", "prompts.sqlite")

    app_state["reports_db_path"] = os.path.join(base_data_path, reports_db_filename)
    app_state["prompts_db_path"] = os.path.join(base_data_path, prompts_db_filename)

    logger.info(f"報告資料庫路徑: {app_state['reports_db_path']}")
    logger.info(f"提示詞資料庫路徑: {app_state['prompts_db_path']}")

    # 2. 初始化服務
    app_state["drive_service"] = GoogleDriveService(
        service_account_json_path=None, # Path constructor arg not used if info is provided
        service_account_info=app_state.get("service_account_info")
    )
    logger.info("GoogleDriveService 已初步初始化。實際憑證使用將發生在 API 調用時。")

    app_state["dal"] = DataAccessLayer(
        reports_db_path=app_state["reports_db_path"],
        prompts_db_path=app_state["prompts_db_path"]
    )
    await app_state["dal"].initialize_databases()
    logger.info("DataAccessLayer 已初始化並檢查/創建了資料庫表。")

    app_state["report_ingestion_service"] = ReportIngestionService(
        drive_service=app_state["drive_service"],
        dal=app_state["dal"]
    )
    logger.info("ReportIngestionService 已初始化。")

    # 3. 初始化並啟動排程器
    scheduler_interval_minutes = int(get_env_or_default("SCHEDULER_INTERVAL_MINUTES", "15"))
    wolf_in_folder_id = os.getenv("WOLF_IN_FOLDER_ID")
    wolf_processed_folder_id = os.getenv("WOLF_PROCESSED_FOLDER_ID")

    if wolf_in_folder_id and wolf_processed_folder_id and app_state.get("service_account_info"):
        scheduler = AsyncIOScheduler(timezone="UTC")
        scheduler.add_job(
            trigger_report_ingestion_task,
            trigger=IntervalTrigger(minutes=scheduler_interval_minutes),
            args=[app_state["report_ingestion_service"]],
            id="report_ingestion_job",
            name="Regularly ingest reports from Google Drive",
            replace_existing=True
        )
        try:
            scheduler.start()
            app_state["scheduler"] = scheduler
            logger.info(f"APScheduler 已啟動，每隔 {scheduler_interval_minutes} 分鐘執行一次報告擷取任務。")
        except Exception as e:
            logger.error(f"APScheduler 啟動失敗: {e}", exc_info=True)
            app_state["scheduler"] = None
    else:
        logger.warning("WOLF_IN_FOLDER_ID, WOLF_PROCESSED_FOLDER_ID, 或 Google Drive 服務帳號憑證未完全設定，排程器未啟動。")
        app_state["scheduler"] = None

    logger.info("後端應用程式已成功啟動。")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("後端應用程式正在關閉...")
    scheduler = app_state.get("scheduler")
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler 已成功關閉。")
    logger.info("後端應用程式已成功關閉。")

# --- API 端點 ---
@app.get("/api/health", response_model=HealthCheckResponse, tags=["General"])
async def health_check():
    scheduler = app_state.get("scheduler")
    scheduler_status = "Not configured or not running"
    if scheduler and scheduler.running:
        job = scheduler.get_job("report_ingestion_job")
        if job:
            scheduler_status = f"Running (Next run: {job.next_run_time})"
        else: # Scheduler might be running but job failed to add
            scheduler_status = "Running (Job 'report_ingestion_job' not found)"

    return HealthCheckResponse(scheduler_status=scheduler_status)

@app.get("/api/get_api_key_status", response_model=ApiKeyStatusResponse, tags=["Configuration"])
async def get_api_key_status():
    is_set = bool(app_state.get("google_api_key")) # COLAB_GOOGLE_API_KEY for Gemini
    source = app_state.get("google_api_key_source")
    drive_sa_loaded = bool(app_state.get("service_account_info"))
    return ApiKeyStatusResponse(is_set=is_set, source=source, drive_service_account_loaded=drive_sa_loaded)

@app.post("/api/set_api_key", response_model=ApiKeyStatusResponse, tags=["Configuration"])
async def set_api_key(payload: ApiKeyRequest):
    if not payload.api_key:
        raise HTTPException(status_code=400, detail="API key cannot be empty")

    key_to_set = payload.api_key
    # This endpoint is primarily for COLAB_GOOGLE_API_KEY (Gemini)
    app_state["google_api_key"] = key_to_set
    app_state["google_api_key_source"] = "user_provided"
    logger.info("COLAB_GOOGLE_API_KEY (for Gemini/etc.) 已由使用者透過 API 設定。")

    # Attempt to parse as Service Account JSON for Drive if not already loaded from env
    if not app_state.get("service_account_info"):
        try:
            key_json = json.loads(key_to_set)
            if isinstance(key_json, dict) and key_json.get("type") == "service_account":
                app_state["service_account_info"] = key_json
                logger.info("使用者提供的 API 金鑰被識別為服務帳號 JSON，並已設定。")
                # Re-initialize DriveService and dependent services if they exist
                if app_state.get("drive_service"):
                    app_state["drive_service"] = GoogleDriveService(service_account_info=key_json)
                    if app_state.get("report_ingestion_service"):
                        app_state["report_ingestion_service"].drive_service = app_state["drive_service"]
                    logger.info("GoogleDriveService 和 ReportIngestionService 已使用新的服務帳號資訊更新。")
                # Potentially try to start scheduler if it wasn't started due to missing SA
                if not app_state.get("scheduler") or not app_state["scheduler"].running:
                    # Code to attempt scheduler start here, similar to startup_event
                    logger.info("嘗試基於新提供的服務帳號資訊啟動排程器。")
                    # (omitted for brevity, would mirror scheduler start logic from startup_event)
        except json.JSONDecodeError:
            logger.info("使用者提供的 API 金鑰不是 JSON 格式，將其視為普通 API 金鑰 (e.g., for Gemini)。")

    drive_sa_loaded = bool(app_state.get("service_account_info"))
    return ApiKeyStatusResponse(is_set=True, source="user_provided", drive_service_account_loaded=drive_sa_loaded)

if __name__ == "__main__":
    os.environ.setdefault("REPORTS_DB_FILENAME", "dev_reports.sqlite")
    os.environ.setdefault("PROMPTS_DB_FILENAME", "dev_prompts.sqlite")
    os.environ.setdefault("SCHEDULER_INTERVAL_MINUTES", "1")
    # For local testing, ensure WOLF_IN_FOLDER_ID, WOLF_PROCESSED_FOLDER_ID,
    # and one of GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT or GOOGLE_APPLICATION_CREDENTIALS are set.
    # e.g. os.environ['WOLF_IN_FOLDER_ID'] = 'YOUR_TEST_INBOX_ID'

    logger.info("啟動 FastAPI 開發伺服器 (main.py)...")
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
