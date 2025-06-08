import os
import logging
import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .services.google_drive_service import GoogleDriveService
from .services.data_access_layer import DataAccessLayer
from .services.report_ingestion_service import ReportIngestionService
from .scheduler_tasks import trigger_report_ingestion_task

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app_state = {
    "google_api_key": None,
    "google_api_key_source": None,
    "service_account_info": None,
    "drive_service": None,
    "dal": None,
    "report_ingestion_service": None,
    "scheduler": None,
    "reports_db_path": None,
    "prompts_db_path": None,
    "drive_service_status": "Not initialized", # Added for more detailed status
}

class ApiKeyRequest(BaseModel):
    api_key: str

class HealthCheckResponse(BaseModel):
    status: str = "OK"
    message: str = "API is running"
    scheduler_status: str = "Not initialized"
    drive_service_status: str = "Not initialized" # Updated field name

class ApiKeyStatusResponse(BaseModel):
    is_set: bool
    source: Optional[str] = None
    drive_service_account_loaded: bool = False

app = FastAPI(
    title="Wolf AI V2.2 Backend",
    description="後端 API 服務，用於 Wolf AI 可觀測性分析平台 V2.2",
    version="2.2.0"
)

def get_env_or_default(var_name: str, default: str) -> str:
    return os.getenv(var_name, default)

@app.on_event("startup")
async def startup_event():
    logger.info("後端應用程式啟動中...")

    # 1. 加載環境變數和配置
    env_api_key = os.getenv("COLAB_GOOGLE_API_KEY")
    if env_api_key:
        app_state["google_api_key"] = env_api_key
        app_state["google_api_key_source"] = "environment"
        logger.info("COLAB_GOOGLE_API_KEY (for Gemini/etc.) 已從環境變數成功加載。")
    else:
        logger.warning("環境變數中未找到 COLAB_GOOGLE_API_KEY。如果需要 Gemini 等服務, 可能需要使用者透過 API 輸入。")

    service_account_json_content = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT")
    service_account_file_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    sa_info_loaded_source = None # To track if SA info came from content or file path

    if service_account_json_content:
        try:
            app_state["service_account_info"] = json.loads(service_account_json_content)
            logger.info("Google Drive 服務帳號金鑰已從 GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT 環境變數加載。")
            sa_info_loaded_source = "json_content"
        except json.JSONDecodeError as e:
            logger.error(f"解析 GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT 失敗: {e}。")
    elif service_account_file_path:
        if os.path.exists(service_account_file_path):
            try:
                with open(service_account_file_path, 'r') as f:
                    app_state["service_account_info"] = json.load(f)
                logger.info(f"Google Drive 服務帳號金鑰已從檔案 {service_account_file_path} 加載。")
                sa_info_loaded_source = "file_path"
            except Exception as e:
                logger.error(f"從 {service_account_file_path} 加載服務帳號金鑰失敗: {e}。")
        else:
            logger.warning(f"GOOGLE_APPLICATION_CREDENTIALS 指向的檔案 {service_account_file_path} 不存在。")

    if not app_state.get("service_account_info"):
        logger.warning("未成功加載 Google Drive 服務帳號金鑰。Google Drive 功能將不可用。")
        app_state["drive_service_status"] = "Credentials not loaded from environment"
    # else:
        # Initial status, will be updated after attempting GDS init
        # app_state["drive_service_status"] = "Credentials loaded from " + sa_info_loaded_source if sa_info_loaded_source else "Credentials error"


    # 資料庫路徑
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(backend_dir)
    base_data_path = os.path.join(project_root, 'data')
    os.makedirs(base_data_path, exist_ok=True)

    reports_db_env_path = os.getenv('REPORTS_DB_PATH')
    prompts_db_env_path = os.getenv('PROMPTS_DB_PATH')

    reports_db_filename = get_env_or_default("REPORTS_DB_FILENAME", "reports.sqlite")
    prompts_db_filename = get_env_or_default("PROMPTS_DB_FILENAME", "prompts.sqlite")

    app_state["reports_db_path"] = reports_db_env_path if reports_db_env_path else os.path.join(base_data_path, reports_db_filename)
    app_state["prompts_db_path"] = prompts_db_env_path if prompts_db_env_path else os.path.join(base_data_path, prompts_db_filename)

    logger.info(f"報告資料庫路徑: {app_state['reports_db_path']}")
    logger.info(f"提示詞資料庫路徑: {app_state['prompts_db_path']}")

    # 2. 初始化服務
    if app_state.get("service_account_info"):
        try:
            app_state["drive_service"] = GoogleDriveService(
                service_account_info=app_state.get("service_account_info")
            )
            logger.info("GoogleDriveService 已初始化。")
            app_state["drive_service_status"] = "Initialized"
        except ValueError as e:
            logger.error(f"GoogleDriveService 初始化失敗 (ValueError): {e}. Drive 功能將不可用。")
            app_state["drive_service"] = None
            app_state["drive_service_status"] = f"Initialization Error: Invalid credentials ({e})"
        except FileNotFoundError as e: # Catch if GDS itself raises this for path
             logger.error(f"GoogleDriveService 初始化失敗 (FileNotFoundError): {e}. Drive 功能將不可用。")
             app_state["drive_service"] = None
             app_state["drive_service_status"] = f"Initialization Error: Credential file not found ({e})"
        except Exception as e:
            logger.error(f"GoogleDriveService 初始化時發生未預期錯誤: {e}", exc_info=True)
            app_state["drive_service"] = None
            app_state["drive_service_status"] = f"Unexpected Initialization Error: {str(e)[:100]}" # Keep error short
    else:
        logger.warning("由於未提供服務帳號憑證，GoogleDriveService 未初始化。")
        app_state["drive_service"] = None
        # Update status only if it wasn't already set to "Credentials not loaded from environment"
        if app_state["drive_service_status"] == "Not initialized":
             app_state["drive_service_status"] = "Not initialized (missing credentials)"

    app_state["dal"] = DataAccessLayer(
        reports_db_path=app_state["reports_db_path"],
        prompts_db_path=app_state["prompts_db_path"]
    )
    await app_state["dal"].initialize_databases()
    logger.info("DataAccessLayer 已初始化並檢查/創建了資料庫表。")

    if app_state.get("drive_service") and app_state.get("dal"): # Check if drive_service is not None
        app_state["report_ingestion_service"] = ReportIngestionService(
            drive_service=app_state["drive_service"],
            dal=app_state["dal"]
        )
        logger.info("ReportIngestionService 已初始化。")
    else:
        logger.warning("由於 DriveService 或 DataAccessLayer 未成功初始化，ReportIngestionService 未初始化。")
        app_state["report_ingestion_service"] = None


    # 3. 初始化並啟動排程器
    scheduler_interval_minutes = int(get_env_or_default("SCHEDULER_INTERVAL_MINUTES", "15"))
    wolf_in_folder_id = os.getenv("WOLF_IN_FOLDER_ID")
    wolf_processed_folder_id = os.getenv("WOLF_PROCESSED_FOLDER_ID")

    if app_state.get("report_ingestion_service"): # Check if report_ingestion_service is not None
        if wolf_in_folder_id and wolf_processed_folder_id:
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
            logger.warning(f"排程器未啟動：WOLF_IN_FOLDER_ID 或 WOLF_PROCESSED_FOLDER_ID 未設定。")
            app_state["scheduler"] = None
    else:
        logger.warning(f"排程器未啟動：ReportIngestionService 未初始化。")
        app_state["scheduler"] = None

    logger.info("後端應用程式啟動流程完成。")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("後端應用程式正在關閉...")
    scheduler = app_state.get("scheduler")
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler 已成功關閉。")
    logger.info("後端應用程式已成功關閉。")

@app.get("/api/health", response_model=HealthCheckResponse, tags=["General"])
async def health_check():
    scheduler = app_state.get("scheduler")
    scheduler_status_msg = "Not configured or not running"
    if scheduler: # If scheduler instance exists
        if scheduler.running:
            job = scheduler.get_job("report_ingestion_job")
            if job:
                scheduler_status_msg = f"Running (Next run: {job.next_run_time})"
            else:
                scheduler_status_msg = "Running (Job 'report_ingestion_job' not found or not added)"
        else: # Scheduler instance exists but not running (e.g. failed to start)
            scheduler_status_msg = "Configured but failed to start or was shut down"
    elif app_state.get("report_ingestion_service") and os.getenv("WOLF_IN_FOLDER_ID") and os.getenv("WOLF_PROCESSED_FOLDER_ID"):
        # This case implies scheduler should have been configured if ReportIngestionService is up
        scheduler_status_msg = "Configured but failed to start (scheduler instance is None)"


    current_drive_status = app_state.get("drive_service_status", "Unknown")
    # If service_account_info was present but drive_service is None, it means init failed.
    if app_state.get("service_account_info") and app_state.get("drive_service") is None:
        # drive_service_status would have been set during the failed init
        pass # current_drive_status already reflects the error
    elif app_state.get("drive_service"): # Service is initialized
        current_drive_status = "Initialized"
    # else: service_account_info was not present, status reflects this.

    return HealthCheckResponse(scheduler_status=scheduler_status_msg, drive_service_status=current_drive_status)

@app.get("/api/get_api_key_status", response_model=ApiKeyStatusResponse, tags=["Configuration"])
async def get_api_key_status():
    is_set = bool(app_state.get("google_api_key"))
    source = app_state.get("google_api_key_source")
    # drive_sa_loaded reflects if service_account_info is present in app_state
    drive_sa_loaded = bool(app_state.get("service_account_info"))
    # For a more accurate status of Drive functionality, one might check app_state["drive_service"] is not None
    # drive_functional = app_state.get("drive_service") is not None
    return ApiKeyStatusResponse(is_set=is_set, source=source, drive_service_account_loaded=drive_sa_loaded)

@app.post("/api/set_api_key", response_model=ApiKeyStatusResponse, tags=["Configuration"])
async def set_api_key(payload: ApiKeyRequest):
    if not payload.api_key:
        raise HTTPException(status_code=400, detail="API key cannot be empty")

    key_to_set = payload.api_key
    app_state["google_api_key"] = key_to_set
    app_state["google_api_key_source"] = "user_provided"
    logger.info("COLAB_GOOGLE_API_KEY (for Gemini/etc.) 已由使用者透過 API 設定。")

    # Attempt to use this key for DriveService ONLY IF service_account_info is not already set from environment
    if not app_state.get("service_account_info"):
        try:
            key_json = json.loads(key_to_set)
            if isinstance(key_json, dict) and key_json.get("type") == "service_account":
                logger.info("使用者提供的 API 金鑰被識別為服務帳號 JSON。嘗試用於 Drive 服務...")

                # Store the new SA info
                app_state["service_account_info"] = key_json

                # Attempt to initialize/re-initialize DriveService
                try:
                    app_state["drive_service"] = GoogleDriveService(service_account_info=key_json)
                    logger.info("GoogleDriveService 已使用使用者提供的服務帳號資訊成功初始化。")
                    app_state["drive_service_status"] = "Initialized (user-provided SA)"

                    # Re-initialize ReportIngestionService if DAL is available
                    if app_state.get("dal"):
                        app_state["report_ingestion_service"] = ReportIngestionService(
                            drive_service=app_state["drive_service"],
                            dal=app_state["dal"]
                        )
                        logger.info("ReportIngestionService 已使用新的 DriveService 實例更新/初始化。")

                        # Try to start scheduler if it wasn't started and conditions are now met
                        if (not app_state.get("scheduler") or not app_state["scheduler"].running) and \
                           os.getenv("WOLF_IN_FOLDER_ID") and os.getenv("WOLF_PROCESSED_FOLDER_ID"):

                            logger.info("嘗試基於新提供的服務帳號資訊啟動排程器...")
                            scheduler_interval_minutes = int(get_env_or_default("SCHEDULER_INTERVAL_MINUTES", "15"))
                            scheduler = AsyncIOScheduler(timezone="UTC")
                            scheduler.add_job(
                                trigger_report_ingestion_task,
                                trigger=IntervalTrigger(minutes=scheduler_interval_minutes),
                                args=[app_state["report_ingestion_service"]],
                                id="report_ingestion_job",
                                name="Regularly ingest reports from Google Drive (post user SA)",
                                replace_existing=True
                            )
                            try:
                                scheduler.start()
                                app_state["scheduler"] = scheduler
                                logger.info(f"APScheduler (post user SA) 已啟動，每隔 {scheduler_interval_minutes} 分鐘執行。")
                            except Exception as e_sched:
                                logger.error(f"APScheduler (post user SA) 啟動失敗: {e_sched}", exc_info=True)
                                app_state["scheduler"] = None # Ensure it's None if start fails
                    else: # DAL not available
                        logger.warning("DataAccessLayer 未初始化，ReportIngestionService 無法配置。")


                except ValueError as e_drive: # From GoogleDriveService init
                    logger.error(f"使用使用者提供的服務帳號資訊初始化 GoogleDriveService 失敗 (ValueError): {e_drive}")
                    app_state["drive_service"] = None # Ensure service is None on failure
                    app_state["report_ingestion_service"] = None # Dependent service also None
                    app_state["drive_service_status"] = f"Init Error (user-provided SA): Invalid credentials ({e_drive})"
                except Exception as e_drive_other: # Any other unexpected error
                    logger.error(f"使用使用者提供的服務帳號資訊初始化 GoogleDriveService 時發生未預期錯誤: {e_drive_other}", exc_info=True)
                    app_state["drive_service"] = None
                    app_state["report_ingestion_service"] = None
                    app_state["drive_service_status"] = f"Unexpected Init Error (user-provided SA): {str(e_drive_other)[:100]}"
        except json.JSONDecodeError:
            logger.info("使用者提供的 API 金鑰不是 JSON 格式，將其視為普通 API 金鑰 (e.g., for Gemini)。")

    final_drive_sa_loaded = app_state.get("drive_service") is not None # True if GDS is initialized
    return ApiKeyStatusResponse(is_set=True, source="user_provided", drive_service_account_loaded=final_drive_sa_loaded)

if __name__ == "__main__":
    os.environ.setdefault("REPORTS_DB_FILENAME", "dev_reports.sqlite")
    os.environ.setdefault("PROMPTS_DB_FILENAME", "dev_prompts.sqlite")
    os.environ.setdefault("SCHEDULER_INTERVAL_MINUTES", "1")
    logger.info("啟動 FastAPI 開發伺服器 (main.py)...")
    port = int(os.getenv("PORT", 8000))
    # Note: uvicorn.run(app, ...) is more standard than uvicorn.run("main:app", ...) when run from __main__
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
