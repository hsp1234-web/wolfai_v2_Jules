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
    "drive_service_status": "Not initialized",
    "critical_config_missing_drive_folders": False,
    "critical_config_missing_sa_credentials": False,
}

class ApiKeyRequest(BaseModel):
    api_key: str

class HealthCheckResponse(BaseModel):
    status: str = "OK"
    message: str = "API is running"
    scheduler_status: str = "Not initialized"
    drive_service_status: str = "Not initialized"
    config_status: str = "檢查中..."
    mode: str

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
    operation_mode = os.getenv("OPERATION_MODE", "transient")
    logger.info(f"偵測到操作模式: {operation_mode}")
    app_state["operation_mode"] = operation_mode

    env_api_key = os.getenv("COLAB_GOOGLE_API_KEY")
    if env_api_key:
        app_state["google_api_key"] = env_api_key
        app_state["google_api_key_source"] = "environment"
        logger.info("COLAB_GOOGLE_API_KEY 已從環境變數成功加載。")
    else:
        logger.warning("環境變數中未找到 COLAB_GOOGLE_API_KEY。")

    service_account_json_content = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT")
    if service_account_json_content:
        try:
            app_state["service_account_info"] = json.loads(service_account_json_content)
            logger.info("Google Drive 服務帳號金鑰已從 GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT 加載。")
        except json.JSONDecodeError as e:
            logger.error(f"解析 GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT 失敗: {e}。")

    if not app_state.get("service_account_info"):
        logger.error("錯誤：Google 服務帳號憑證未設定。")
        app_state["critical_config_missing_sa_credentials"] = True
        app_state["drive_service_status"] = "錯誤：服務帳號憑證未設定"

    wolf_in_folder_id_env = os.getenv("WOLF_IN_FOLDER_ID")
    wolf_processed_folder_id_env = os.getenv("WOLF_PROCESSED_FOLDER_ID")
    if not wolf_in_folder_id_env or not wolf_processed_folder_id_env:
        logger.warning("警告：必要的 Google Drive 資料夾 ID 未完整設定。")
        app_state["critical_config_missing_drive_folders"] = True
    else:
        logger.info("Google Drive 資料夾 ID 已讀取。")

    reports_db_env_path = os.getenv('REPORTS_DB_PATH')
    prompts_db_env_path = os.getenv('PROMPTS_DB_PATH')
    base_data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    os.makedirs(base_data_path, exist_ok=True)
    app_state["reports_db_path"] = reports_db_env_path if reports_db_env_path else os.path.join(base_data_path, "reports.sqlite")
    app_state["prompts_db_path"] = prompts_db_env_path if prompts_db_env_path else os.path.join(base_data_path, "prompts.sqlite")

    logger.info(f"報告資料庫路徑設定為: {app_state['reports_db_path']}")
    logger.info(f"提示詞資料庫路徑設定為: {app_state['prompts_db_path']}")

    app_state["dal"] = DataAccessLayer(
        reports_db_path=app_state["reports_db_path"],
        prompts_db_path=app_state["prompts_db_path"]
    )
    await app_state["dal"].initialize_databases()
    logger.info("DataAccessLayer 已初始化。")

    if operation_mode == "persistent":
        logger.info("持久模式：嘗試初始化 Google Drive 相關服務...")
        if not app_state["critical_config_missing_sa_credentials"]:
            try:
                app_state["drive_service"] = GoogleDriveService(service_account_info=app_state.get("service_account_info"))
                logger.info("GoogleDriveService 已成功初始化。")
                app_state["drive_service_status"] = "已初始化 (持久模式)"
            except Exception as e:
                logger.error(f"GoogleDriveService 初始化失敗: {e}", exc_info=True)
                app_state["drive_service"] = None
                app_state["drive_service_status"] = f"初始化錯誤: {e}"
        else:
            logger.warning("因服務帳號憑證缺失，GoogleDriveService 未初始化。")
            app_state["drive_service"] = None

        if app_state.get("drive_service") and app_state.get("dal"):
            app_state["report_ingestion_service"] = ReportIngestionService(
                drive_service=app_state["drive_service"],
                dal=app_state["dal"]
            )
            logger.info("ReportIngestionService 已初始化。")
        else:
            logger.warning("因依賴項未滿足，ReportIngestionService 未初始化。")
            app_state["report_ingestion_service"] = None

        # --- 修正後的排程器啟動邏輯 ---
        if app_state.get("report_ingestion_service"):
            if not app_state["critical_config_missing_drive_folders"]:
                scheduler_interval_minutes = int(get_env_or_default("SCHEDULER_INTERVAL_MINUTES", "15"))
                scheduler = AsyncIOScheduler(timezone="UTC")
                scheduler.add_job(
                    trigger_report_ingestion_task,
                    trigger=IntervalTrigger(minutes=scheduler_interval_minutes),
                    args=[app_state["report_ingestion_service"]],
                    id="report_ingestion_job",
                    name="定期從 Google Drive 擷取報告",
                    replace_existing=True
                )
                try:
                    scheduler.start()
                    app_state["scheduler"] = scheduler
                    logger.info(f"APScheduler 排程器已啟動，每隔 {scheduler_interval_minutes} 分鐘執行。")
                except Exception as e:
                    logger.error(f"APScheduler 排程器啟動失敗: {e}", exc_info=True)
                    app_state["scheduler"] = None
            else:
                logger.warning("排程器未啟動：因 Google Drive 資料夾 ID 未完整設定。")
                app_state["scheduler"] = None
        else:
            logger.warning("排程器未啟動：因 ReportIngestionService 未初始化。")
            app_state["scheduler"] = None
        # --- 修正結束 ---

    else: # 暫存模式
        logger.info("暫存模式：跳過 Google Drive 相關服務的初始化。")
        app_state["drive_service"] = None
        app_state["drive_service_status"] = "暫存模式下未啟用"
        app_state["report_ingestion_service"] = None
        app_state["scheduler"] = None

    logger.info("後端應用程式啟動流程完成。")


# ... (檔案的其餘部分保持不變) ...

@app.on_event("shutdown")
async def shutdown_event():
    # ... (此函數內容不變) ...
    pass

@app.get("/api/health", response_model=HealthCheckResponse, tags=["General"])
async def health_check():
    # ... (此函數內容不變) ...
    pass

@app.get("/api/get_api_key_status", response_model=ApiKeyStatusResponse, tags=["設定"])
async def get_api_key_status():
    # ... (此函數內容不變) ...
    pass

@app.post("/api/set_api_key", response_model=ApiKeyStatusResponse, tags=["設定"])
async def set_api_key(payload: ApiKeyRequest):
    # ... (此函數內容不變) ...
    pass

if __name__ == "__main__":
    # ... (此區塊內容不變) ...
    pass

# ... (檔案結尾的 app.openapi_tags 等設定保持不變) ...
