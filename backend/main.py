import os
import logging
import json
import httpx # For frontend check
import pytz # For timezone aware datetime
from datetime import datetime # For datetime objects
from fastapi import FastAPI, HTTPException, Header, APIRouter, Body
from contextlib import asynccontextmanager # Import from standard library
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, SecretStr # Added SecretStr
from typing import Optional, Dict, Any, List # Added List
from pythonjsonlogger import jsonlogger

import google.generativeai as genai

from .config import settings
from .services.google_drive_service import GoogleDriveService
from .services.data_access_layer import DataAccessLayer
from .services.parsing_service import ParsingService
from .services.gemini_service import GeminiService
from .services.report_ingestion_service import ReportIngestionService
from .services.analysis_service import AnalysisService # Added AnalysisService
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

class OriginalApiKeyStatusResponse(BaseModel): # Renamed original ApiKeyStatusResponse
    """API 金鑰設定狀態的回應模型。 (舊版，涉及單一 Gemini 金鑰)"""
    is_set: bool = Field(..., description="指示 Gemini API 金鑰當前是否已在後端設定（無論是來自環境變數或使用者輸入）。")
    source: Optional[str] = Field(default=None, description="API 金鑰的來源。可能的值：'environment/config'（來自設定檔案或環境變數），'user_input'（由使用者透過 API 設定）。如果金鑰未設定，則為 null。")
    drive_service_account_loaded: bool = Field(..., description="指示 Google Drive 服務帳號金鑰是否已成功從設定中加載並解析。")
    gemini_configured: bool = Field(..., description="指示 Gemini AI 服務當前是否已使用有效的 API 金鑰成功配置。")

class KeyStatusResponse(BaseModel):
    """通用API金鑰設定狀態的回應模型。"""
    GOOGLE_API_KEY: str = Field(default="未設定", description="Google Gemini API 金鑰的狀態。")
    API_KEY_FRED: str = Field(default="未設定", description="用於 FRED 的 API 金鑰狀態。")
    API_KEY_FINMIND: str = Field(default="未設定", description="用於 FinMind 的 API 金鑰狀態。")
    API_KEY_FINNHUB: str = Field(default="未設定", description="用於 Finnhub 的 API 金鑰狀態。")
    API_KEY_FMP: str = Field(default="未設定", description="用於 Financial Modeling Prep 的 API 金鑰狀態。")
    ALPHA_VANTAGE_API_KEY: str = Field(default="未設定", description="用於 Alpha Vantage 的 API 金鑰狀態。")
    DEEPSEEK_API_KEY: str = Field(default="未設定", description="用於 DeepSeek 的 API 金鑰狀態。")
    # 為了兼容性和提供完整資訊，可以選擇性加入舊的特定狀態欄位
    legacy_gemini_api_key_is_set: Optional[bool] = Field(None, description="[舊版欄位] 指示 Gemini API 金鑰是否已在後端設定。")
    legacy_gemini_api_key_source: Optional[str] = Field(None, description="[舊版欄位] Gemini API 金鑰的來源。")
    drive_service_account_loaded: Optional[bool] = Field(None, description="指示 Google Drive 服務帳戶金鑰是否已成功從設定中加載並解析。")
    gemini_service_configured: Optional[bool] = Field(None, description="指示 Gemini AI 服務當前是否已使用有效的 API 金鑰成功配置。")

class SetKeysRequest(BaseModel):
    """用於動態設定一個或多個 API 金鑰的請求模型。"""
    GOOGLE_API_KEY: Optional[str] = Field(None, description="Google Gemini API 金鑰。")
    API_KEY_FRED: Optional[str] = Field(None, description="FRED API 金鑰。")
    API_KEY_FINMIND: Optional[str] = Field(None, description="FinMind API 金鑰。")
    API_KEY_FINNHUB: Optional[str] = Field(None, description="Finnhub API 金鑰。")
    API_KEY_FMP: Optional[str] = Field(None, description="Financial Modeling Prep API 金鑰。")
    ALPHA_VANTAGE_API_KEY: Optional[str] = Field(None, description="Alpha Vantage API 金鑰。")
    DEEPSEEK_API_KEY: Optional[str] = Field(None, description="DeepSeek API 金鑰。")
    # 注意：不在此處包含 GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT，因其結構複雜且通常透過環境變數設定。

    class Config:
        extra = "ignore" # 忽略請求中未在模型中定義的額外欄位

class ReportRequest(BaseModel):
    """用於請求生成分析報告的模型。"""
    data_dimensions: List[str] = Field(..., description="用於生成報告的數據維度列表。")

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
    # 更新金鑰讀取邏輯以使用 GOOGLE_API_KEY (來自 config.py 的更改)
    if settings.GOOGLE_API_KEY: # Changed from COLAB_GOOGLE_API_KEY
        api_key_value = settings.GOOGLE_API_KEY.get_secret_value()
        if api_key_value:
            app_state["google_api_key"] = api_key_value # This state is used by GeminiService internally
            app_state["google_api_key_source"] = "environment/config"
            logger.info("GOOGLE_API_KEY 已從設定成功加載。", extra={"props": {"source": "environment/config"}}) # Log message updated
        else:
            logger.warning("設定中的 GOOGLE_API_KEY 為空值。Gemini 功能可能受限。", extra={"props": {"config_issue": "empty_api_key"}}) # Log message updated
            app_state["google_api_key_source"] = "environment/config (空值)"
    else:
        logger.warning("設定中未找到 GOOGLE_API_KEY。Gemini 功能可能受限。", extra={"props": {"config_issue": "missing_api_key"}}) # Log message updated
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
@app.get("/api/v1/health", response_model=HealthCheckResponse, tags=["健康檢查"], summary="執行基礎健康檢查")
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

@app.get("/api/v1/health/verbose", response_model=VerboseHealthCheckResponse, tags=["健康檢查"], summary="執行詳細健康檢查", include_in_schema=False)
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

@app.get("/api/v1/get_api_key_status", response_model=KeyStatusResponse, tags=["設定"], summary="獲取所有API金鑰的設定狀態") # Changed response_model
async def get_key_status() -> KeyStatusResponse: # Function name changed and return type hint updated
    """
    獲取在 `backend/config.py` 中定義的所有主要 API 金鑰的設定狀態。

    返回一個 JSON 物件，其中每個金鑰對應一個字串，說明其狀態 ("已設定" 或 "未設定")。
    同時也包含應用程式內部使用的 Gemini 金鑰狀態及 Drive 服務帳號狀態。
    """
    key_statuses_dict: Dict[str, Any] = {}

    # List of API keys to check from settings
    # These names must match the attribute names in backend/config.py's Settings class
    api_key_names = [
        "GOOGLE_API_KEY", "API_KEY_FRED", "API_KEY_FINMIND",
        "API_KEY_FINNHUB", "API_KEY_FMP", "ALPHA_VANTAGE_API_KEY",
        "DEEPSEEK_API_KEY"
    ]

    for key_name in api_key_names:
        key_value: Optional[SecretStr] = getattr(settings, key_name, None)
        if key_value and key_value.get_secret_value(): # Check if SecretStr has a value
            key_statuses_dict[key_name] = "已設定"
        else:
            key_statuses_dict[key_name] = "未設定"

    # Add other relevant statuses from app_state for completeness in the new response model
    gemini_service_instance = app_state.get("gemini_service")
    gemini_configured_status = gemini_service_instance.is_configured if gemini_service_instance else False

    key_statuses_dict["legacy_gemini_api_key_is_set"] = bool(app_state.get("google_api_key"))
    key_statuses_dict["legacy_gemini_api_key_source"] = app_state.get("google_api_key_source")
    key_statuses_dict["drive_service_account_loaded"] = bool(app_state.get("service_account_info"))
    key_statuses_dict["gemini_service_configured"] = gemini_configured_status

    return KeyStatusResponse(**key_statuses_dict)

# The original /api/get_api_key_status is now effectively replaced by /api/get_key_status.
# If strict preservation of the old endpoint with its exact old model is needed,
# it would be renamed e.g. /api/get_legacy_gemini_key_status and use OriginalApiKeyStatusResponse.
# For this task, we are replacing it as per instructions to create a NEW endpoint for all keys.

@app.post("/api/v1/set_api_key", response_model=OriginalApiKeyStatusResponse, tags=["設定"], summary="設定 API 金鑰 (僅限 Gemini，舊版端點)") # response_model changed to OriginalApiKeyStatusResponse
async def set_api_key(payload: ApiKeyRequest):
    """
    設定或更新用於 Google Gemini AI 服務的 API 金鑰。 (此為舊版端點，主要影響 Gemini 金鑰)

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

        # Also update os.environ and the global settings object
        os.environ["GOOGLE_API_KEY"] = payload.api_key
        settings.GOOGLE_API_KEY = SecretStr(payload.api_key)
        logger.info(f"GOOGLE_API_KEY 已在 os.environ 和 settings 中更新，並暫存於 app_state。", extra={"props": {"request_id": request_id, "source": "user_input"}})

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

        # Construct and return the OriginalApiKeyStatusResponse
        # This part needs to fetch the state as the old endpoint would have.
        return OriginalApiKeyStatusResponse(
            is_set=bool(app_state.get("google_api_key")),
            source=app_state.get("google_api_key_source"),
            drive_service_account_loaded=bool(app_state.get("service_account_info")),
            gemini_configured=gemini_service_instance.is_configured # Use the updated status
        )
    except HTTPException as http_exc: # 重新引發已知的 HTTP 異常
        raise http_exc
    except Exception as e: # 捕獲其他所有未預期錯誤
        logger.error(f"設定 API 金鑰時發生未預期錯誤: {e}", exc_info=True, extra={"props": {"api_endpoint": "/api/set_api_key", "request_id": request_id}})
        raise HTTPException(status_code=500, detail="設定 API 金鑰時發生內部伺服器錯誤。")

@app.post("/api/v1/set_keys", summary="動態設定一個或多個API金鑰", tags=["設定"])
async def set_keys(payload: SetKeysRequest = Body(...)):
    """
    動態設定一個或多個 API 金鑰。
    提交的任何金鑰都將更新應用程式的環境變數和運行時設定。
    如果為某個金鑰提供的值為 null 或空字串，則會嘗試清除該金鑰的設定。

    **注意：** 更改某些金鑰（如 `GOOGLE_API_KEY`）後，相關服務（如 `GeminiService`）
    的行為可能會在下一次使用時才反映更新後的金鑰，這取決於服務的實例管理和初始化方式。
    對於 `GeminiService`，由於其在 `app_state` 中通常作為單例存在，並且金鑰在 `__init__` 時配置，
    因此直接修改 `settings` 物件後，若要使現有 `GeminiService` 實例立即使用新金鑰，
    可能需要額外的重新配置步驟或重新啟動服務。
    當前實現會更新 `settings`，這將影響後續新創建的 `GeminiService` 實例。
    對於 `app_state` 中管理的 `GeminiService` 實例，如果 `GOOGLE_API_KEY` 發生變化，
    `genai.configure` 會被調用，`is_configured` 狀態也會更新。
    """
    updated_keys = []
    request_id = os.urandom(8).hex()
    logger.info(f"接收到 /api/set_keys 請求 (ID: {request_id})", extra={"props": {"api_endpoint": "/api/set_keys", "request_id": request_id, "payload": payload.model_dump_json(exclude_none=True)}})

    for key_name, value in payload.model_dump(exclude_none=False).items(): # Use exclude_none=False to iterate even if value is None
        # 只處理 Settings 中實際定義的 API 金鑰 (且為 SecretStr 類型)
        if hasattr(settings, key_name) and isinstance(getattr(settings, key_name, None), (SecretStr, type(None))):
            if value is not None: # 值被提供了 (包括空字串)
                os.environ[key_name] = value
                setattr(settings, key_name, SecretStr(value) if value else None)
                logger.info(f"API 金鑰 '{key_name}' 已在環境變數和設定中更新。", extra={"props": {"request_id": request_id, "key_name": key_name, "action": "updated" if value else "cleared"}})
                if key_name == "GOOGLE_API_KEY": # 特別處理 Gemini 金鑰的即時重配置
                    app_state["google_api_key"] = value if value else None
                    app_state["google_api_key_source"] = "user_input (set_keys)"
                    gemini_service_instance = app_state.get("gemini_service")
                    if gemini_service_instance:
                        try:
                            if value:
                                genai.configure(api_key=value)
                                gemini_service_instance.is_configured = True
                                logger.info(f"GeminiService 已使用新的 GOOGLE_API_KEY 重新配置。", extra={"props": {"request_id": request_id, "reconfig_status": "success"}})
                            else:
                                # 如果金鑰被清空，理想情況下應使 genai 不再使用任何金鑰，
                                # 但 genai 庫可能沒有直接的 "unconfigure" 方法。
                                # 將 is_configured 設為 False 是關鍵。
                                gemini_service_instance.is_configured = False
                                logger.info(f"GOOGLE_API_KEY 已被清除，GeminiService 標記為未配置。", extra={"props": {"request_id": request_id, "reconfig_status": "cleared"}})
                        except Exception as e_reconfig:
                            gemini_service_instance.is_configured = False
                            logger.error(f"使用新的 GOOGLE_API_KEY 重新配置 GeminiService 時失敗: {e_reconfig}", exc_info=True, extra={"props": {"request_id": request_id, "reconfig_status": "failure", "error": str(e_reconfig)}})
                updated_keys.append(key_name)
            elif hasattr(settings, key_name) and getattr(settings, key_name) is not None : # payload 中 key 為 None，但 settings 中有值，表示要清除
                if key_name in os.environ:
                    del os.environ[key_name]
                setattr(settings, key_name, None)
                logger.info(f"API 金鑰 '{key_name}' 已從環境變數和設定中清除。", extra={"props": {"request_id": request_id, "key_name": key_name, "action": "explicitly_cleared"}})
                if key_name == "GOOGLE_API_KEY": # 同樣處理 Gemini
                    app_state["google_api_key"] = None
                    app_state["google_api_key_source"] = "user_input (set_keys_cleared)"
                    gemini_service_instance = app_state.get("gemini_service")
                    if gemini_service_instance:
                        gemini_service_instance.is_configured = False
                        logger.info(f"GOOGLE_API_KEY 已被清除，GeminiService 標記為未配置。", extra={"props": {"request_id": request_id, "reconfig_status": "cleared_on_none"}})
                updated_keys.append(key_name)


    if not updated_keys:
        logger.info(f"未提供任何有效金鑰進行更新 (請求 ID: {request_id})", extra={"props": {"request_id": request_id, "action": "no_valid_keys_provided"}})
        return JSONResponse(status_code=200, content={"message": "未提供任何有效金鑰進行更新。請確保金鑰名稱正確且在允許的列表中。", "updated_keys": updated_keys})

    return JSONResponse(status_code=200, content={"message": f"API 金鑰已處理。受影響的金鑰: {', '.join(updated_keys)}", "updated_keys": updated_keys})

@app.post("/api/v1/reports/generate", tags=["報告分析"], summary="根據指定維度生成分析報告")
async def generate_report_endpoint(request: ReportRequest):
    """
    根據提供的數據維度列表生成綜合分析報告。

    此端點接收一個包含 `data_dimensions` 列表的請求體。
    後端將使用 `AnalysisService` 來處理這些維度並生成一份模擬的分析報告。
    """
    request_id = os.urandom(8).hex()
    logger.info(
        f"接收到生成報告請求 (ID: {request_id})",
        extra={"props": {"api_endpoint": "/api/v1/reports/generate", "request_id": request_id, "data_dimensions": request.data_dimensions}}
    )
    try:
        # 在實際應用中, AnalysisService 可能會透過依賴注入 (FastAPI Depends) 來管理
        # 這有助於管理服務的生命週期和依賴關係 (例如 DataAccessLayer)
        analysis_service = AnalysisService() # 直接實例化服務
        report = analysis_service.generate_report(request.data_dimensions)
        logger.info(
            f"報告已成功生成 (請求 ID: {request_id})",
            extra={"props": {"request_id": request_id, "report_summary": report.get("summary"), "status": report.get("status")}}
        )
        return report
    except Exception as e:
        logger.error(
            f"生成報告時發生錯誤 (請求 ID: {request_id}): {e}",
            exc_info=True, # 包含堆疊追蹤
            extra={"props": {"api_endpoint": "/api/v1/reports/generate", "request_id": request_id, "error": str(e)}}
        )
        # 返回一個標準化的錯誤回應
        raise HTTPException(status_code=500, detail=f"生成報告時發生內部伺服器錯誤: {str(e)}")

app.openapi_tags = [
    {"name": "健康檢查", "description": "應用程式健康狀態相關端點。"},
    {"name": "通用操作", "description": "提供應用程式基本資訊或通用功能的端點。"},
    {"name": "設定", "description": "與應用程式設定相關的 API 端點。"},
    {"name": "報告分析", "description": "與生成和管理分析報告相關的端點。"}, # Added new tag
]

if __name__ == "__main__":
    import uvicorn
    logger.info("以開發模式在本機啟動 Uvicorn 伺服器...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
