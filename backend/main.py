import os
import logging
import json
import httpx # For frontend check
import pytz # For timezone aware datetime
from datetime import datetime # For datetime objects
from fastapi import FastAPI, HTTPException, Header
from contextlib import asynccontextmanager # Import from standard library
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from pythonjsonlogger import jsonlogger

import google.generativeai as genai

from .config import settings
from .services.google_drive_service import GoogleDriveService
from .services.data_access_layer import DataAccessLayer
from .services.parsing_service import ParsingService
from .services.gemini_service import GeminiService
from .services.report_ingestion_service import ReportIngestionService
from .scheduler_tasks import trigger_report_ingestion_task

logger = logging.getLogger(__name__)

app_state = {
    "google_api_key": None, "google_api_key_source": None, "service_account_info": None,
    "drive_service": None, "dal": None, "parsing_service": None, "gemini_service": None,
    "report_ingestion_service": None, "scheduler": None, "reports_db_path": None,
    "prompts_db_path": None, "drive_service_status": "未初始化",
    "critical_config_missing_drive_folders": False, "critical_config_missing_sa_credentials": False,
    "operation_mode": "transient"
}

# --- Pydantic Models ---
class ApiKeyRequest(BaseModel):
    """用於設定 API 金鑰的請求模型。"""
    api_key: str = Field(..., description="要設定的 API 金鑰字串。此金鑰將用於與 Google Gemini AI 服務的交互。")

class HealthCheckResponse(BaseModel):
    """標準健康檢查端點的回應模型，提供應用程式總體狀態的快速概覽。"""
    status: str = Field(default="正常", description="API 的總體健康狀態，例如 '正常', '警告', '錯誤'。")
    message: str = Field(default="API 正常運行中", description="關於 API 當前狀態的簡短描述性訊息。")
    scheduler_status: str = Field(default="未初始化", description="背景排程服務的運行狀態。")
    drive_service_status: str = Field(default="未初始化", description="Google Drive 服務的初始化和連接狀態。")
    config_status: str = Field(default="檢查中...", description="關鍵應用程式設定的狀態（例如，憑證、資料夾ID）。")
    mode: str = Field(default="未知", description="應用程式當前的操作模式 (例如：'transient' 表示暫存模式，'persistent' 表示持久模式)。")
    gemini_status: str = Field(default="未初始化", description="Google Gemini AI 服務的配置和可用性狀態。")

class ApiKeyStatusResponse(BaseModel):
    """API 金鑰設定狀態的回應模型。"""
    is_set: bool = Field(..., description="指示 Gemini API 金鑰當前是否已在後端設定（無論是來自環境變數或使用者輸入）。")
    source: Optional[str] = Field(default=None, description="API 金鑰的來源。可能的值：'environment/config'（來自設定檔案或環境變數），'user_input'（由使用者透過 API 設定）。如果金鑰未設定，則為 null。")
    drive_service_account_loaded: bool = Field(..., description="指示 Google Drive 服務帳號金鑰是否已成功從設定中加載並解析。")
    gemini_configured: bool = Field(..., description="指示 Gemini AI 服務當前是否已使用有效的 API 金鑰成功配置。")

class ComponentStatus(BaseModel):
    """詳細健康檢查中單個應用程式組件的狀態模型。"""
    status: str = Field(..., description="組件的運行狀態。常見值：'正常', '異常', '未配置', '未啟用', '設定錯誤', '嚴重故障'。")
    details: Optional[str] = Field(default=None, description="關於組件當前狀態的額外詳細資訊或錯誤訊息摘要。")

class SchedulerComponentStatus(ComponentStatus):
    """排程器組件的詳細狀態回報模型。"""
    next_run_time: Optional[datetime] = Field(default=None, description="主要排程任務（如報告擷取）的下次預計運行時間（UTC 時區）。如果排程器未運行或任務未排程，則可能為 null。")

class FilesystemComponentStatus(ComponentStatus):
    """檔案系統相關檢查（如暫存目錄權限）的狀態回報模型。"""
    temp_dir_path: Optional[str] = Field(default=None, description="被檢查的應用程式暫存目錄的絕對路徑。")

class FrontendComponentStatus(ComponentStatus):
    """前端服務可達性檢查的狀態回報模型（從後端角度探測）。"""
    frontend_url: Optional[str] = Field(default=None, description="用於探測的前端服務 URL（通常是 http://localhost:3000）。")

class VerboseHealthCheckResponse(BaseModel):
    """深度健康檢查端點 (`/api/health/verbose`) 的回應模型，包含各關鍵組件的詳細狀態。"""
    overall_status: str = Field(..., description="整個應用程式的總體健康狀態。可能的值：'全部正常', '部分異常', '嚴重故障'。")
    timestamp: datetime = Field(..., description="健康檢查執行的時間戳（台北時區）。")
    database_status: ComponentStatus = Field(..., description="資料庫連接和基本操作的狀態。")
    gemini_api_status: ComponentStatus = Field(..., description="Gemini AI 服務的配置和（初步）可連線性狀態。")
    google_drive_status: ComponentStatus = Field(..., description="Google Drive 服務的配置和（初步）可連線性狀態（主要在持久模式下）。")
    scheduler_status: SchedulerComponentStatus = Field(..., description="背景排程服務及其主要任務的狀態。")
    filesystem_status: FilesystemComponentStatus = Field(..., description="應用程式所需檔案系統操作（如暫存目錄讀寫權限）的狀態。")
    frontend_service_status: FrontendComponentStatus = Field(..., description="前端服務的可達性狀態（從後端角度進行探測）。")

# --- Lifespan Management (應用程式生命週期管理) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 應用程式的生命週期管理器。

    在應用程式啟動時執行初始化操作，並在應用程式關閉時執行清理操作。
    目前的初始化操作包括：
    - 配置 JSON 格式的日誌記錄器。
    - 從設定中加載並初始化應用程式狀態 (app_state)，包括 API 金鑰、服務帳號資訊、資料庫路徑等。
    - 初始化各個服務：DataAccessLayer, ParsingService, GeminiService, GoogleDriveService (如果適用), ReportIngestionService。
    - 如果應用程式以 "persistent" (持久) 模式運行，則啟動 APScheduler 排程器以執行背景任務。

    在應用程式關閉時：
    - 如果排程器正在運行，則將其關閉。
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    for handler in root_logger.handlers[:]: root_logger.removeHandler(handler)
    log_handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(module)s %(funcName)s %(lineno)d %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger_name"}
    )
    log_handler.setFormatter(formatter)
    root_logger.addHandler(log_handler)
    logger.info("JSON Logger 已配置。後端應用程式啟動中...")
    app_state["operation_mode"] = settings.OPERATION_MODE
    logger.info(f"偵測到操作模式: {app_state['operation_mode']}", extra={"props": {"operation_mode": app_state['operation_mode']}})
    if settings.COLAB_GOOGLE_API_KEY:
        api_key_value = settings.COLAB_GOOGLE_API_KEY.get_secret_value()
        if api_key_value:
            app_state["google_api_key"] = api_key_value
            app_state["google_api_key_source"] = "environment/config"
            logger.info("COLAB_GOOGLE_API_KEY 已從設定成功加載。", extra={"props": {"source": "environment/config"}})
        else:
            logger.warning("設定中的 COLAB_GOOGLE_API_KEY 為空值。Gemini 功能可能受限。", extra={"props": {"config_issue": "empty_api_key"}})
            app_state["google_api_key_source"] = "environment/config (空值)"
    else:
        logger.warning("設定中未找到 COLAB_GOOGLE_API_KEY。Gemini 功能可能受限。", extra={"props": {"config_issue": "missing_api_key"}})
    if settings.GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT:
        sa_content_str = settings.GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT.get_secret_value()
        if sa_content_str:
            try:
                app_state["service_account_info"] = json.loads(sa_content_str)
                logger.info("Google Drive 服務帳號金鑰已從設定成功加載。", extra={"props": {"service_account_loaded": True}})
            except json.JSONDecodeError as e:
                logger.error(f"解析來自設定的 GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT 失敗: {e}.", exc_info=True, extra={"props": {"service_account_error": str(e)}})
                app_state["service_account_info"] = None
        else:
            logger.warning("設定中的 GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT 為空值。Drive 功能可能受限。", extra={"props": {"config_issue": "empty_sa_json"}})
    if not app_state.get("service_account_info"):
        logger.error("錯誤：Google 服務帳號憑證未設定、為空或解析失敗。Drive 功能可能受限。", extra={"props": {"critical_config_error": "missing_service_account"}})
        app_state["critical_config_missing_sa_credentials"] = True
        app_state["drive_service_status"] = "錯誤：服務帳號憑證未設定、為空或解析失敗"
    if not settings.WOLF_IN_FOLDER_ID or not settings.WOLF_PROCESSED_FOLDER_ID:
        logger.warning("警告：必要的 Google Drive 資料夾 ID 未在設定中完整設定。Drive 相關排程器功能可能受限。", extra={"props": {"config_issue": "missing_drive_folder_ids"}})
        app_state["critical_config_missing_drive_folders"] = True
    else:
        logger.info(f"Google Drive 資料夾 ID 已從設定讀取。", extra={"props": {"WOLF_IN_FOLDER_ID": settings.WOLF_IN_FOLDER_ID, "WOLF_PROCESSED_FOLDER_ID": settings.WOLF_PROCESSED_FOLDER_ID }})
    SERVICE_DIR_MAIN = os.path.dirname(os.path.abspath(__file__))
    BACKEND_DIR_MAIN = SERVICE_DIR_MAIN
    app_state["temp_download_dir"] = os.path.join(BACKEND_DIR_MAIN, 'data', 'temp_downloads')
    os.makedirs(app_state["temp_download_dir"], exist_ok=True)
    logger.info(f"應用程式暫存下載目錄設定於: {app_state['temp_download_dir']}", extra={"props": {"temp_dir": app_state['temp_download_dir']}})
    base_data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    os.makedirs(base_data_path, exist_ok=True)
    app_state["reports_db_path"] = settings.REPORTS_DB_PATH or os.path.join(base_data_path, "reports.sqlite")
    app_state["prompts_db_path"] = settings.PROMPTS_DB_PATH or os.path.join(base_data_path, "prompts.sqlite")
    logger.info(f"報告資料庫路徑設定為: {app_state['reports_db_path']}", extra={"props":{"db_path":app_state['reports_db_path']}})
    logger.info(f"提示詞資料庫路徑設定為: {app_state['prompts_db_path']}", extra={"props":{"db_path":app_state['prompts_db_path']}})
    try:
        app_state["dal"] = DataAccessLayer(reports_db_path=app_state["reports_db_path"], prompts_db_path=app_state["prompts_db_path"])
        await app_state["dal"].initialize_databases()
        logger.info("DataAccessLayer 已初始化。", extra={"props": {"service_initialized": "DAL"}})
    except Exception as e_dal:
        logger.fatal(f"DataAccessLayer 初始化失敗，應用程式可能無法正常運作: {e_dal}", exc_info=True, extra={"props": {"service_failed": "DAL", "error": str(e_dal)}})
        app_state["dal"] = None
    app_state["parsing_service"] = ParsingService()
    app_state["gemini_service"] = GeminiService()
    gem_service = app_state.get("gemini_service")
    logger.info(f"GeminiService 已初始化 (配置狀態: {'已配置' if gem_service and gem_service.is_configured else '未配置/金鑰缺失'})。", extra={"props": {"service_initialized": "GeminiService", "configured": gem_service.is_configured if gem_service else False}})
    if app_state["operation_mode"] == "persistent":
        logger.info("持久模式：嘗試初始化 Google Drive 相關服務...", extra={"props": {"mode_details": "persistent_drive_init"}})
        if not app_state["critical_config_missing_sa_credentials"]:
            try:
                app_state["drive_service"] = GoogleDriveService(service_account_info=app_state.get("service_account_info"))
                logger.info("GoogleDriveService 已成功初始化。", extra={"props": {"service_initialized": "GoogleDriveService"}})
                app_state["drive_service_status"] = "已初始化 (持久模式)"
            except Exception as e:
                logger.error(f"GoogleDriveService 初始化失敗: {e}", exc_info=True, extra={"props": {"service_failed": "GoogleDriveService", "error": str(e)}})
                app_state["drive_service"] = None
                app_state["drive_service_status"] = f"初始化錯誤: {e}"
        else:
            logger.warning("因服務帳號憑證缺失，GoogleDriveService 未初始化。", extra={"props": {"service_skipped": "GoogleDriveService", "reason": "missing_credentials"}})
            app_state["drive_service"] = None
            app_state["drive_service_status"] = "未初始化 (憑證缺失)"
    else:
        logger.info("暫存模式：GoogleDriveService 未啟用。", extra={"props": {"mode_details": "transient_drive_skip"}})
        app_state["drive_service"] = None
        app_state["drive_service_status"] = "暫存模式下未啟用"
    if app_state.get("dal") and app_state.get("parsing_service") and app_state.get("gemini_service"):
        app_state["report_ingestion_service"] = ReportIngestionService(
            drive_service=app_state.get("drive_service"), dal=app_state["dal"],
            parsing_service=app_state["parsing_service"], gemini_service=app_state["gemini_service"]
        )
    else:
        logger.error("因核心依賴項 (DAL, ParsingService, GeminiService) 未完全初始化，ReportIngestionService 未能初始化。", extra={"props": {"service_failed_dependency": "ReportIngestionService"}})
        app_state["report_ingestion_service"] = None
    if app_state["operation_mode"] == "persistent" and app_state.get("report_ingestion_service"):
        if not app_state["critical_config_missing_drive_folders"] and app_state.get("drive_service"):
            scheduler = AsyncIOScheduler(timezone="UTC")
            scheduler.add_job( trigger_report_ingestion_task, trigger=IntervalTrigger(minutes=settings.SCHEDULER_INTERVAL_MINUTES),
                args=[app_state["report_ingestion_service"]], id="report_ingestion_job", name="定期從 Google Drive 擷取報告", replace_existing=True )
            try:
                scheduler.start()
                app_state["scheduler"] = scheduler
                logger.info(f"APScheduler 排程器已啟動，每隔 {settings.SCHEDULER_INTERVAL_MINUTES} 分鐘執行。", extra={"props": {"scheduler_interval_minutes": settings.SCHEDULER_INTERVAL_MINUTES}})
            except Exception as e:
                logger.error(f"APScheduler 排程器啟動失敗: {e}", exc_info=True, extra={"props": {"scheduler_failed": True, "error": str(e)}})
                app_state["scheduler"] = None
        else:
            logger.warning("排程器未啟動：因 Google Drive 資料夾 ID 未完整設定或 DriveService 未初始化。", extra={"props": {"scheduler_skipped": True, "reason": "drive_config_or_service_issue"}})
            app_state["scheduler"] = None
    elif app_state["operation_mode"] == "persistent":
        logger.warning("排程器未啟動：因 ReportIngestionService 未初始化。", extra={"props": {"scheduler_skipped": True, "reason": "report_ingestion_service_not_init"}})
        app_state["scheduler"] = None
    else:
        logger.info("暫存模式：排程器未啟用。", extra={"props": {"scheduler_skipped": True, "reason": "transient_mode"}})
        app_state["scheduler"] = None
    logger.info("後端應用程式啟動流程完成。")
    yield
    logger.info("後端應用程式關閉中...")
    if app_state.get("scheduler") and app_state["scheduler"].running:
        logger.info("正在關閉 APScheduler 排程器...")
        app_state["scheduler"].shutdown()
        logger.info("APScheduler 排程器已關閉。")
    logger.info("後端應用程式已關閉。")

app = FastAPI(
    title="Wolf AI V2.2 Backend",
    description="後端 API 服務，用於 Wolf AI 可觀測性分析平台 V2.2",
    version="2.2.0",
    lifespan=lifespan
)

# --- API Endpoints ---
@app.get("/api/health", response_model=HealthCheckResponse, tags=["健康檢查"], summary="執行基礎健康檢查")
async def health_check():
    """
    執行基礎健康檢查。

    此端點提供應用程式的總體健康狀態，包括排程器、Drive 服務、
    關鍵設定以及 Gemini AI 服務的配置狀態。
    """
    try:
        config_parts = []
        if app_state.get("critical_config_missing_sa_credentials"): config_parts.append("缺少服務帳號憑證")
        if app_state.get("critical_config_missing_drive_folders"): config_parts.append("缺少 Drive 資料夾 ID")
        config_status_msg = "所有關鍵設定正常" if not config_parts else "警告: " + "； ".join(config_parts)
        scheduler_status = "未啟用或未初始化"
        scheduler_instance = app_state.get("scheduler")
        if scheduler_instance: scheduler_status = "執行中" if scheduler_instance.running else "已停止"
        elif app_state.get("operation_mode") == "persistent": scheduler_status = "未啟動 (設定或依賴缺失)"
        gemini_service_instance = app_state.get("gemini_service")
        gemini_status_msg = "未初始化"
        if gemini_service_instance: gemini_status_msg = "已配置API金鑰" if gemini_service_instance.is_configured else "未配置API金鑰"
        return HealthCheckResponse(
            status="正常" if not config_parts and (not gemini_service_instance or gemini_service_instance.is_configured) else "警告",
            message="API 正常運行中" if not config_parts else "API 運行中但有設定問題",
            scheduler_status=scheduler_status, drive_service_status=app_state.get("drive_service_status", "未初始化"),
            config_status=config_status_msg, mode=app_state.get("operation_mode", "未知"),
            gemini_status=gemini_status_msg )
    except Exception as e:
        logger.error(f"執行健康檢查時發生未預期錯誤: {e}", exc_info=True, extra={"props": {"api_endpoint": "/api/health"}})
        return HealthCheckResponse( status="錯誤", message=f"健康檢查端點異常: {str(e)}", scheduler_status="未知",
            drive_service_status="未知", config_status="未知", mode=app_state.get("operation_mode", "未知"), gemini_status="未知" )

@app.get("/api/health/verbose", response_model=VerboseHealthCheckResponse, tags=["健康檢查"], summary="執行詳細健康檢查", include_in_schema=False)
async def verbose_health_check():
    """
    執行詳細的健康檢查。

    此端點提供應用程式各個關鍵組件的詳細狀態報告，
    包括資料庫連接、AI 服務、Drive 服務、排程器、檔案系統權限以及前端服務的可達性。
    此端點通常不包含在公開的 OpenAPI schema 中，主要用於內部監控或調試。
    """
    current_time_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
    current_time_taipei = current_time_utc.astimezone(pytz.timezone('Asia/Taipei'))
    statuses: Dict[str, Any] = {
        "database_status": {"status": "未知", "details": None}, "gemini_api_status": {"status": "未知", "details": None},
        "google_drive_status": {"status": "未知", "details": None},
        "scheduler_status": {"status": "未知", "details": None, "next_run_time": None},
        "filesystem_status": {"status": "未知", "details": None, "temp_dir_path": app_state.get("temp_download_dir")},
        "frontend_service_status": {"status": "未知", "details": None, "frontend_url": "http://localhost:3000 (預期)"},
    }
    all_ok = True
    dal_service = app_state.get("dal")
    if dal_service:
        try:
            async with aiosqlite.connect(dal_service.reports_db_path) as db: await db.execute("SELECT 1")
            statuses["database_status"]["status"] = "正常"
            statuses["database_status"]["details"] = f"成功連接到報告資料庫 ({dal_service.reports_db_path})"
        except Exception as e_db:
            logger.error(f"資料庫健康檢查失敗: {e_db}", exc_info=True, extra={"props": {"health_check_component": "database", "error": str(e_db)}})
            statuses["database_status"]["status"] = "異常"; statuses["database_status"]["details"] = f"連接或查詢資料庫失敗: {str(e_db)}"; all_ok = False
    else: statuses["database_status"]["status"] = "嚴重故障"; statuses["database_status"]["details"] = "資料存取層 (DAL) 未初始化。"; all_ok = False
    gemini_service = app_state.get("gemini_service")
    if gemini_service:
        if gemini_service.is_configured:
            statuses["gemini_api_status"]["status"] = "已配置"; statuses["gemini_api_status"]["details"] = "API 金鑰已設定。(注意：未執行即時連線測試)"
        else: statuses["gemini_api_status"]["status"] = "未配置"; statuses["gemini_api_status"]["details"] = "API 金鑰未在設定中提供或為空。"; all_ok = False
    else: statuses["gemini_api_status"]["status"] = "嚴重故障"; statuses["gemini_api_status"]["details"] = "GeminiService 未初始化。"; all_ok = False
    drive_service = app_state.get("drive_service")
    if app_state.get("operation_mode") == "persistent":
        if drive_service:
            if app_state.get("critical_config_missing_sa_credentials"): statuses["google_drive_status"]["status"] = "設定錯誤"; statuses["google_drive_status"]["details"] = "服務帳號憑證缺失或無效。"; all_ok = False
            elif app_state.get("critical_config_missing_drive_folders"): statuses["google_drive_status"]["status"] = "設定錯誤"; statuses["google_drive_status"]["details"] = "必要的 Drive 資料夾 ID 未設定。"; all_ok = False
            else: statuses["google_drive_status"]["status"] = "已初始化"; statuses["google_drive_status"]["details"] = "DriveService 已在持久模式下初始化。(注意：未執行即時連線測試)"
        else: statuses["google_drive_status"]["status"] = "異常"; statuses["google_drive_status"]["details"] = "持久模式下 DriveService 未能成功初始化。"; all_ok = False
    else: statuses["google_drive_status"]["status"] = "暫存模式下未啟用"; statuses["google_drive_status"]["details"] = "應用程式以暫存模式運行。"
    scheduler_instance = app_state.get("scheduler")
    if scheduler_instance:
        if scheduler_instance.running:
            statuses["scheduler_status"]["status"] = "運行中"
            try:
                job = scheduler_instance.get_job("report_ingestion_job")
                if job and job.next_run_time:
                    next_run_utc = job.next_run_time
                    if next_run_utc.tzinfo is None: next_run_utc = pytz.utc.localize(next_run_utc)
                    statuses["scheduler_status"]["next_run_time"] = next_run_utc
                    statuses["scheduler_status"]["details"] = f"報告擷取任務已排程，下次運行: {next_run_utc.isoformat()}"
                else: statuses["scheduler_status"]["details"] = "報告擷取任務存在但無下次運行時間。"
            except Exception as e_job:
                logger.error(f"獲取排程器任務詳情失敗: {e_job}", exc_info=True, extra={"props": {"health_check_component": "scheduler", "error": str(e_job)}})
                statuses["scheduler_status"]["details"] = f"無法獲取任務詳情: {str(e_job)}"
        else: statuses["scheduler_status"]["status"] = "未運行"; statuses["scheduler_status"]["details"] = "排程器已初始化但目前未運行。"; all_ok = False
    elif app_state.get("operation_mode") == "persistent": statuses["scheduler_status"]["status"] = "未初始化"; statuses["scheduler_status"]["details"] = "持久模式下排程器未能啟動 (可能由於設定或依賴問題)。"; all_ok = False
    else: statuses["scheduler_status"]["status"] = "暫存模式下未啟用"
    temp_dir = app_state.get("temp_download_dir", "/app/data/temp_downloads")
    statuses["filesystem_status"]["temp_dir_path"] = temp_dir
    if os.path.exists(temp_dir) and os.path.isdir(temp_dir):
        if os.access(temp_dir, os.R_OK) and os.access(temp_dir, os.W_OK): statuses["filesystem_status"]["status"] = "可讀寫"; statuses["filesystem_status"]["details"] = f"暫存目錄 '{temp_dir}' 存在且權限正常。"
        else: statuses["filesystem_status"]["status"] = "權限異常"; statuses["filesystem_status"]["details"] = f"暫存目錄 '{temp_dir}' 存在但讀寫權限不足。"; all_ok = False
    else: statuses["filesystem_status"]["status"] = "目錄不存在"; statuses["filesystem_status"]["details"] = f"暫存目錄 '{temp_dir}' 不存在。"; all_ok = False
    frontend_url = "http://localhost:3000"
    statuses["frontend_service_status"]["frontend_url"] = frontend_url
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(frontend_url)
            if 200 <= response.status_code < 400: statuses["frontend_service_status"]["status"] = "可達"; statuses["frontend_service_status"]["details"] = f"前端服務在 {frontend_url} 回應狀態碼 {response.status_code}。"
            else: statuses["frontend_service_status"]["status"] = "回應異常"; statuses["frontend_service_status"]["details"] = f"前端服務在 {frontend_url} 回應錯誤狀態碼: {response.status_code}。"; all_ok = False
    except httpx.TimeoutException:
        logger.warning(f"探測前端服務 ({frontend_url}) 超時。", extra={"props": {"health_check_component": "frontend", "error": "timeout"}})
        statuses["frontend_service_status"]["status"] = "請求超時"; statuses["frontend_service_status"]["details"] = f"連接前端服務 {frontend_url} 超時。"; all_ok = False
    except httpx.RequestError as e_frontend:
        logger.warning(f"探測前端服務 ({frontend_url}) 發生錯誤: {e_frontend}", extra={"props": {"health_check_component": "frontend", "error": str(e_frontend)}})
        statuses["frontend_service_status"]["status"] = "無法連線"; statuses["frontend_service_status"]["details"] = f"連接前端服務 {frontend_url} 失敗: {str(e_frontend)}。"; all_ok = False
    overall = "全部正常"
    if not all_ok:
        if statuses["database_status"]["status"] == "嚴重故障" or statuses["gemini_api_status"]["status"] == "嚴重故障": overall = "嚴重故障"
        else: overall = "部分異常"
    return VerboseHealthCheckResponse(
        overall_status=overall, timestamp=current_time_taipei,
        database_status=ComponentStatus(**statuses["database_status"]),
        gemini_api_status=ComponentStatus(**statuses["gemini_api_status"]),
        google_drive_status=ComponentStatus(**statuses["google_drive_status"]),
        scheduler_status=SchedulerComponentStatus(**statuses["scheduler_status"]),
        filesystem_status=FilesystemComponentStatus(**statuses["filesystem_status"]),
        frontend_service_status=FrontendComponentStatus(**statuses["frontend_service_status"]) )

@app.get("/api/get_api_key_status", response_model=ApiKeyStatusResponse, tags=["設定"], summary="獲取 API 金鑰設定狀態")
async def get_api_key_status():
    """
    獲取當前 API 金鑰的設定狀態。

    此端點返回 Gemini API 金鑰是否已設定、其來源（環境變數或使用者輸入）、
    Google Drive 服務帳號是否已加載，以及 Gemini 服務是否已成功配置。
    """
    try:
        gemini_service_instance = app_state.get("gemini_service")
        gemini_configured_status = gemini_service_instance.is_configured if gemini_service_instance else False
        return ApiKeyStatusResponse(
            is_set=bool(app_state.get("google_api_key")), source=app_state.get("google_api_key_source"),
            drive_service_account_loaded=bool(app_state.get("service_account_info")),
            gemini_configured=gemini_configured_status )
    except Exception as e:
        logger.error(f"獲取 API 金鑰狀態時發生未預期錯誤: {e}", exc_info=True, extra={"props": {"api_endpoint": "/api/get_api_key_status"}})
        raise HTTPException(status_code=500, detail="獲取 API 金鑰狀態時發生內部伺服器錯誤。")

@app.post("/api/set_api_key", response_model=ApiKeyStatusResponse, tags=["設定"], summary="設定 API 金鑰")
async def set_api_key(payload: ApiKeyRequest):
    """
    設定或更新用於 Google Gemini AI 服務的 API 金鑰。

    使用者可以通過此端點在運行時提供 API 金鑰。
    提交的金鑰將被暫存，並用於重新配置 Gemini 服務。
    成功設定後，將返回更新後的 API 金鑰狀態。
    如果提供的金鑰為空，將返回 400 錯誤。
    如果 Gemini 服務未初始化，將返回 503 錯誤。
    """
    request_id = os.urandom(8).hex()
    logger.info(f"接收到設定 API 金鑰請求。", extra={"props": {"api_endpoint": "/api/set_api_key", "request_id": request_id}})
    try:
        if not payload.api_key or not payload.api_key.strip():
            logger.warning("設定 API 金鑰請求失敗：API 金鑰不得為空。", extra={"props": {"request_id": request_id, "validation_error": "empty_api_key"}})
            raise HTTPException(status_code=400, detail="API 金鑰不得為空。")

        # 更新應用程式狀態中的 API 金鑰及其來源
        app_state["google_api_key"] = payload.api_key
        app_state["google_api_key_source"] = "user_input"
        logger.info(f"Google API Key 已透過 API 暫存於 app_state。", extra={"props": {"request_id": request_id, "source": "user_input"}})

        gemini_service_instance = app_state.get("gemini_service")
        if not gemini_service_instance:
            logger.error("GeminiService 未初始化，無法使用新金鑰進行配置。", extra={"props": {"request_id": request_id, "internal_error": "gemini_service_not_init"}})
            raise HTTPException(status_code=503, detail="Gemini服務內部未正確初始化，無法設定API金鑰。")

        logger.info("正在使用新的 API 金鑰重新配置 GeminiService...", extra={"props": {"request_id": request_id}})
        try:
            # 直接調用 genai.configure 來更新金鑰
            genai.configure(api_key=payload.api_key)
            gemini_service_instance.is_configured = True # 更新服務實例的配置狀態
            logger.info("GeminiService 已成功使用新金鑰重新配置。", extra={"props": {"request_id": request_id, "reconfig_status": "success"}})
        except Exception as e_reconfig:
            gemini_service_instance.is_configured = False # 配置失敗，更新狀態
            logger.error(f"使用新 API 金鑰重新配置 GeminiService 時失敗: {e_reconfig}", exc_info=True, extra={"props": {"request_id": request_id, "reconfig_status": "failure", "error": str(e_reconfig)}})
            # 即使重新配置失敗，也返回當前狀態，讓客戶端知道金鑰已設定但可能無效

        return await get_api_key_status() # 返回更新後的金鑰狀態
    except HTTPException as http_exc: # 重新引發已知的 HTTP 異常
        raise http_exc
    except Exception as e: # 捕獲其他所有未預期錯誤
        logger.error(f"設定 API 金鑰時發生未預期錯誤: {e}", exc_info=True, extra={"props": {"api_endpoint": "/api/set_api_key", "request_id": request_id}})
        raise HTTPException(status_code=500, detail="設定 API 金鑰時發生內部伺服器錯誤。")

app.openapi_tags = [
    {"name": "健康檢查", "description": "應用程式健康狀態相關端點。"},
    {"name": "通用操作", "description": "提供應用程式基本資訊或通用功能的端點。"},
    {"name": "設定", "description": "與應用程式設定相關的 API 端點。"},
]

if __name__ == "__main__":
    import uvicorn
    logger.info("以開發模式在本機啟動 Uvicorn 伺服器...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
