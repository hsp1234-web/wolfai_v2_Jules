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
    "critical_config_missing_drive_folders": False, # 新增狀態標記
    "critical_config_missing_sa_credentials": False, # 新增狀態標記
}

class ApiKeyRequest(BaseModel):
    api_key: str

class HealthCheckResponse(BaseModel):
    status: str = "OK"
    message: str = "API is running"
    scheduler_status: str = "Not initialized"
    drive_service_status: str = "Not initialized" # Updated field name
    config_status: str = "檢查中..." # 新增欄位，用於更詳細的配置狀態
    mode: str # 新增欄位: 當前操作模式 (例如 "transient" 或 "persistent")

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

    # 0. 讀取操作模式 (由 Colab 筆記本設定的環境變數)
    # OPERATION_MODE 環境變數決定了應用程式是否應嘗試使用 Google Drive 進行資料持久化。
    # "persistent" (持久模式): 啟用 Google Drive 整合，資料將儲存於使用者的 Drive。
    # "transient" (暫存模式): 禁用 Google Drive 整合，資料僅儲存在當前會話，結束後遺失。預設為 transient。
    operation_mode = os.getenv("OPERATION_MODE", "transient")
    logger.info(f"偵測到操作模式: {operation_mode}")
    app_state["operation_mode"] = operation_mode # 將操作模式存儲於應用程式狀態中，供其他部分使用

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
        # logger.warning("未成功加載 Google Drive 服務帳號金鑰。Google Drive 功能將不可用。") # 將由更具體的錯誤取代
        logger.error("錯誤：Google 服務帳號憑證 (GOOGLE_APPLICATION_CREDENTIALS 或 GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT) 未設定。")
        app_state["critical_config_missing_sa_credentials"] = True
        app_state["drive_service_status"] = "錯誤：服務帳號憑證未設定" # 更新狀態以反映問題
    # else: # 憑證已加載其一
        # logger.info(f"Google Drive 服務帳號憑證已從 {sa_info_loaded_source} 加載。") # 這條日誌已在各自的 if/elif 塊中處理過了

    # 檢查必要的 Drive Folder ID
    wolf_in_folder_id_env = os.getenv("WOLF_IN_FOLDER_ID")
    wolf_processed_folder_id_env = os.getenv("WOLF_PROCESSED_FOLDER_ID")
    if not wolf_in_folder_id_env or not wolf_processed_folder_id_env:
        logger.warning("警告：必要的 Google Drive 資料夾 ID (WOLF_IN_FOLDER_ID 或 WOLF_PROCESSED_FOLDER_ID) 未完整設定。排程器相關功能可能無法正常運作。")
        app_state["critical_config_missing_drive_folders"] = True
    else:
        logger.info("Google Drive 資料夾 ID (WOLF_IN_FOLDER_ID, WOLF_PROCESSED_FOLDER_ID) 已讀取。")


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

    logger.info(f"報告資料庫路徑設定為: {app_state['reports_db_path']}")
    logger.info(f"提示詞資料庫路徑設定為: {app_state['prompts_db_path']}")

    # 2. 初始化服務 (DataAccessLayer 在所有模式下都初始化)
    app_state["dal"] = DataAccessLayer(
        reports_db_path=app_state["reports_db_path"],
        prompts_db_path=app_state["prompts_db_path"]
    )
    await app_state["dal"].initialize_databases() # DAL 初始化應在兩種模式下都執行
    logger.info("DataAccessLayer 已初始化並檢查/創建了資料庫表。")

    # 根據操作模式，決定是否初始化 Google Drive 相關的服務 (GoogleDriveService, ReportIngestionService, APScheduler)
    if operation_mode == "persistent":
        # 持久模式下，應用程式將嘗試連接 Google Drive 並啟用所有相關功能。
        logger.info("持久模式：嘗試初始化 Google Drive 相關服務...")

        # GoogleDriveService 初始化:
        # 僅在持久模式下，並且成功加載了 Google 服務帳號憑證 (來自環境變數) 時進行。
        if not app_state["critical_config_missing_sa_credentials"]:
            if app_state.get("service_account_info"):
                try:
                    app_state["drive_service"] = GoogleDriveService(
                        service_account_info=app_state.get("service_account_info")
                    )
                    logger.info("GoogleDriveService 已成功初始化 (持久模式)。")
                    app_state["drive_service_status"] = "已初始化 (持久模式)"
                except ValueError as e:
                    logger.error(f"GoogleDriveService 初始化失敗 (ValueError): {e}。Google Drive 功能將不可用 (持久模式)。")
                    app_state["drive_service"] = None
                    app_state["drive_service_status"] = f"初始化錯誤 (持久模式)：無效的憑證 ({e})"
                except FileNotFoundError as e:
                     logger.error(f"GoogleDriveService 初始化失敗 (FileNotFoundError): {e}。Google Drive 功能將不可用 (持久模式)。")
                     app_state["drive_service"] = None
                     app_state["drive_service_status"] = f"初始化錯誤 (持久模式)：找不到憑證檔案 ({e})"
                except Exception as e:
                    logger.error(f"GoogleDriveService 初始化時發生未預期錯誤: {e} (持久模式)", exc_info=True)
                    app_state["drive_service"] = None
                    app_state["drive_service_status"] = f"未預期的初始化錯誤 (持久模式): {str(e)[:100]}"
            else:
                logger.warning("服務帳號資訊為空，即使未標記為嚴重憑證缺失。GoogleDriveService 未初始化 (持久模式)。")
                app_state["drive_service"] = None
                app_state["drive_service_status"] = "未初始化 (持久模式，服務帳號資訊為空)"
        else:
            logger.warning("由於 Google 服務帳號憑證缺失，GoogleDriveService 未初始化 (持久模式)。")
            app_state["drive_service"] = None
            # drive_service_status 已在前面憑證檢查部分設定過 (例如 "錯誤：服務帳號憑證未設定")

        # ReportIngestionService 初始化:
        # 僅在持久模式下，並且 GoogleDriveService 和 DataAccessLayer 都已成功初始化時進行。
        if app_state.get("drive_service") and app_state.get("dal"):
            app_state["report_ingestion_service"] = ReportIngestionService(
                drive_service=app_state["drive_service"],
                dal=app_state["dal"]
            )
            logger.info("ReportIngestionService 已初始化 (持久模式)。")
        else:
            missing_deps_ingestion = []
            if not app_state.get("drive_service"): missing_deps_ingestion.append("GoogleDriveService")
            if not app_state.get("dal"): missing_deps_ingestion.append("DataAccessLayer")
            logger.warning(f"由於 { ' 和 '.join(missing_deps_ingestion) } 未成功初始化，ReportIngestionService 未初始化 (持久模式)。")
            app_state["report_ingestion_service"] = None

        # APScheduler (排程器) 初始化與啟動:
        # 僅在持久模式下，ReportIngestionService 已初始化，且必要的 Drive Folder ID 已設定時進行。
        # 排程器負責定期觸發報告擷取任務。
        if app_state.get("report_ingestion_service"):
            if not app_state["critical_config_missing_drive_folders"]: # 檢查 Drive Folder ID 是否已設定
                scheduler_interval_minutes = int(get_env_or_default("SCHEDULER_INTERVAL_MINUTES", "15"))
                scheduler = AsyncIOScheduler(timezone="UTC") # 使用 UTC 以避免時區問題
                scheduler.add_job(
                    trigger_report_ingestion_task,
                    trigger=IntervalTrigger(minutes=scheduler_interval_minutes),
                    args=[app_state["report_ingestion_service"]],
                    id="report_ingestion_job",
                    name="定期從 Google Drive 擷取報告 (持久模式)",
                    replace_existing=True
                )
                try:
                    scheduler.start()
                    app_state["scheduler"] = scheduler
                    logger.info(f"APScheduler 排程器已啟動 (持久模式)，每隔 {scheduler_interval_minutes} 分鐘執行一次報告擷取任務。")
                except Exception as e:
                    logger.error(f"APScheduler 排程器啟動失敗: {e} (持久模式)", exc_info=True)
                    app_state["scheduler"] = None
            else:
                logger.warning("排程器未啟動 (持久模式)：由於 Google Drive 資料夾 ID 未完整設定。")
                app_state["scheduler"] = None
        else:
            logger.warning("排程器未啟動 (持久模式)：由於 ReportIngestionService 未初始化。")
                    app_state["scheduler"] = None # 確保啟動失敗時 scheduler 為 None
            else:
                logger.warning("排程器未啟動 (持久模式)：由於 Google Drive 資料夾 ID (WOLF_IN_FOLDER_ID 或 WOLF_PROCESSED_FOLDER_ID) 未完整設定。")
                app_state["scheduler"] = None
        else:
            logger.warning("排程器未啟動 (持久模式)：由於 ReportIngestionService 未初始化。")
            app_state["scheduler"] = None
    else: # transient mode (暫存模式)
        # 在暫存模式下，所有與 Google Drive 持久化相關的服務都不會被初始化。
        # 資料庫將使用本地臨時路徑 (由 run_in_colab.ipynb 設定)。
        logger.info("暫存模式：跳過 GoogleDriveService, ReportIngestionService, 和 APScheduler 的初始化。")
        app_state["drive_service"] = None
        app_state["drive_service_status"] = "暫存模式下未啟用" # 明確指出 Drive 服務在暫存模式下的狀態
        app_state["report_ingestion_service"] = None
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
    # 從 app_state 獲取在啟動時設定的操作模式，預設為 "未知" 以處理可能的邊界情況。
    operation_mode = app_state.get("operation_mode", "未知")

    # 根據操作模式和排程器狀態決定 scheduler_status_msg。
    scheduler_status_msg = f"未設定或未執行 (模式: {operation_mode})"
    if operation_mode == "persistent":
        if scheduler:
            if scheduler.running:
                job = scheduler.get_job("report_ingestion_job")
                if job:
                    scheduler_status_msg = f"執行中 (模式: persistent, 下次執行: {job.next_run_time})"
                else:
                    scheduler_status_msg = "執行中 (模式: persistent, 任務 'report_ingestion_job' 未找到)"
            else:
                scheduler_status_msg = "已配置但啟動失敗或已關閉 (模式: persistent)"
        elif app_state.get("report_ingestion_service") and not app_state.get("critical_config_missing_drive_folders"):
            scheduler_status_msg = "已配置但啟動失敗 (模式: persistent, 排程器實例為空)"
        elif app_state.get("critical_config_missing_drive_folders"):
            scheduler_status_msg = "未啟動 (模式: persistent, Google Drive 資料夾 ID 未完整設定)"
        else: # 其他持久模式下排程器未啟動的情況
             scheduler_status_msg = f"未啟動 (模式: persistent, ReportIngestionService 未初始化或未知原因)"
    else: # transient mode
        scheduler_status_msg = f"暫存模式下未啟用"


    current_drive_status = app_state.get("drive_service_status", f"未知狀態 (模式: {operation_mode})")
    # 如果 service_account_info 存在但 drive_service 為 None，說明初始化失敗。
    # current_drive_status 應已在啟動時設定了具體的錯誤訊息。
    # 如果 drive_service 成功初始化，current_drive_status 會是 "已初始化"。

    config_messages = []
    if app_state.get("critical_config_missing_drive_folders"):
        config_messages.append("警告：Google Drive 資料夾 ID 未完整設定。")
    if app_state.get("critical_config_missing_sa_credentials"):
        config_messages.append("錯誤：Google 服務帳號憑證未設定。")

    # Drive service status 可能已經從初始化中指出了錯誤
    # 避免在 config_messages 中重複報告 Drive Service 的憑證問題，如果它已經由 critical_config_missing_sa_credentials 捕獲
    if ("錯誤" in current_drive_status or "Error" in current_drive_status or "失敗" in current_drive_status) and \
       not (app_state.get("critical_config_missing_sa_credentials") and "憑證" in current_drive_status):
        config_messages.append(f"Google Drive 服務: {current_drive_status}")
    elif current_drive_status == "已初始化" and not config_messages: # 如果 GDS 初始化成功且沒有其他配置問題
        pass # 不需要添加額外的 GDS 狀態訊息
    elif current_drive_status != "已初始化" and current_drive_status != "未知狀態" and \
         not (app_state.get("critical_config_missing_sa_credentials") and "憑證" in current_drive_status):
        # 捕獲其他非 "已初始化" 狀態，同時避免重複憑證問題
        config_messages.append(f"Google Drive 服務: {current_drive_status}")


    if not config_messages: # 如果沒有任何警告或錯誤訊息
        final_config_status = "設定完整" # Chinese message
    else:
        final_config_status = " | ".join(config_messages)

    # 從 app_state 獲取當前操作模式，用於包含在回應中。
    current_operation_mode = app_state.get("operation_mode", "transient") # 預設為 "transient" 以防萬一

    return HealthCheckResponse(
        scheduler_status=scheduler_status_msg,
        drive_service_status=current_drive_status,
        config_status=final_config_status,
        mode=current_operation_mode # 在回應中明確包含當前操作模式
    )

@app.get("/api/get_api_key_status", response_model=ApiKeyStatusResponse, tags=["設定"])
async def get_api_key_status():
    is_set = bool(app_state.get("google_api_key"))
    source = app_state.get("google_api_key_source")
    api_key_is_set = bool(app_state.get("google_api_key")) # 重複，可以移除一個
    api_key_source = app_state.get("google_api_key_source", "未設定") # 若未設定來源，提供預設文字
    operation_mode = app_state.get("operation_mode", "未知") # 獲取當前操作模式

    # drive_service_account_loaded 的狀態取決於操作模式：
    # - 在 "persistent" 模式下，它反映 Google Drive 服務帳號是否已成功加載且 DriveService 正常運作。
    # - 在 "transient" 模式下，此狀態應為 False，因為 Drive 服務不在此模式下使用。
    sa_loaded_and_functional = False
    if operation_mode == "persistent":
        # 持久模式下，檢查服務帳號憑證是否未缺失，且 DriveService 實例是否存在。
        sa_loaded_and_functional = not app_state.get("critical_config_missing_sa_credentials", False) and \
                                   app_state.get("drive_service") is not None
    elif operation_mode == "transient":
        # 暫存模式下，Drive 服務帳號不適用/不加載。
        sa_loaded_and_functional = False

    return ApiKeyStatusResponse(
        is_set=api_key_is_set, # AI服務金鑰是否已設定
        source=api_key_source, # AI服務金鑰的來源
        drive_service_account_loaded=sa_loaded_and_functional # Drive服務帳號是否已加載並可用 (僅持久模式下有意義)
    )

@app.post("/api/set_api_key", response_model=ApiKeyStatusResponse, tags=["設定"])
async def set_api_key(payload: ApiKeyRequest):
    if not payload.api_key:
        raise HTTPException(status_code=400, detail="API 金鑰不能為空")

    key_to_set = payload.api_key
    app_state["google_api_key"] = key_to_set # 設定通用 AI 金鑰 (如 Gemini)
    app_state["google_api_key_source"] = "使用者提供" # 記錄金鑰來源
    logger.info("COLAB_GOOGLE_API_KEY (用於 Gemini 等服務) 已由使用者透過 API 設定。")
    operation_mode = app_state.get("operation_mode", "transient") # 獲取當前操作模式

    # 如果使用者提供的金鑰是服務帳號 JSON，則嘗試用其設定 Google Drive 服務。
    # 此操作僅在 "persistent" (持久) 模式下，且先前服務帳號憑證未成功從環境變數加載時進行。
    # 在 "transient" (暫存) 模式下，即使提供了服務帳號 JSON，也不會初始化 DriveService。
    if operation_mode == "persistent":
        # 檢查是否需要設定 Drive 服務：1. 先前標記為缺失，或 2. Drive 服務帳號資訊為空
        if app_state.get("critical_config_missing_sa_credentials", True) or not app_state.get("service_account_info"):
            try:
                key_json = json.loads(key_to_set) # 嘗試解析為 JSON
                # 檢查解析後的 JSON 是否為有效的服務帳號格式
                if isinstance(key_json, dict) and key_json.get("type") == "service_account":
                    logger.info("使用者提供的 API 金鑰被識別為服務帳號 JSON。嘗試用於 Google Drive 服務 (持久模式)...")
                    app_state["service_account_info"] = key_json # 儲存服務帳號資訊
                    app_state["critical_config_missing_sa_credentials"] = False # 重設憑證缺失標記

                    # 嘗試重新初始化 GoogleDriveService 及相關依賴服務 (ReportIngestionService, APScheduler)
                    try:
                        # 如果已存在 DriveService 實例 (例如，先前因其他原因初始化失敗)，先清理
                        if app_state.get("drive_service"):
                            logger.info("正在替換已有的 DriveService 實例 (持久模式)...")
                            app_state["drive_service"] = None
                            app_state["report_ingestion_service"] = None
                            if app_state.get("scheduler") and app_state["scheduler"].running: # 如果排程器正在運行
                                app_state["scheduler"].shutdown(wait=False) # 關閉排程器
                                app_state["scheduler"] = None
                                logger.info("已關閉並移除現有排程器 (持久模式)，準備使用新憑證重啟。")

                        # 初始化 DriveService
                        app_state["drive_service"] = GoogleDriveService(service_account_info=key_json)
                        logger.info("GoogleDriveService 已使用使用者提供的服務帳號資訊成功初始化 (持久模式)。")
                        app_state["drive_service_status"] = "已初始化 (使用者提供的服務帳號, 持久模式)"

                        # 重新初始化 ReportIngestionService (依賴 DriveService 和 DAL)
                        if app_state.get("dal"): # 確保 DAL 存在
                            app_state["report_ingestion_service"] = ReportIngestionService(
                                drive_service=app_state["drive_service"],
                                dal=app_state["dal"]
                            )
                            logger.info("ReportIngestionService 已使用新的 DriveService 實例更新/初始化 (持久模式)。")

                            # 如果條件滿足 (Drive Folder ID 已設定)，嘗試啟動/重啟排程器
                            if (not app_state.get("scheduler") or not app_state["scheduler"].running) and \
                               not app_state["critical_config_missing_drive_folders"]: # 檢查 Drive Folder ID
                                logger.info("嘗試基於新提供的服務帳號資訊啟動排程器 (持久模式)...")
                                scheduler_interval_minutes = int(get_env_or_default("SCHEDULER_INTERVAL_MINUTES", "15"))
                                new_scheduler = AsyncIOScheduler(timezone="UTC") # 創建新的排程器實例
                                new_scheduler.add_job(
                                    trigger_report_ingestion_task,
                                    trigger=IntervalTrigger(minutes=scheduler_interval_minutes),
                                    args=[app_state["report_ingestion_service"]],
                                    id="report_ingestion_job",
                                    name="定期從 Google Drive 擷取報告 (使用者提供SA後, 持久模式)",
                                    replace_existing=True
                                )
                                try:
                                    new_scheduler.start()
                                    app_state["scheduler"] = new_scheduler
                                    logger.info(f"APScheduler (使用者提供SA後, 持久模式) 已啟動，每隔 {scheduler_interval_minutes} 分鐘執行。")
                                except Exception as e_sched:
                                    logger.error(f"APScheduler (使用者提供SA後, 持久模式) 啟動失敗: {e_sched}", exc_info=True)
                                    app_state["scheduler"] = None
                        else:
                            logger.warning("DataAccessLayer 未初始化，ReportIngestionService 無法配置 (持久模式)。")

                    except ValueError as e_drive:
                        logger.error(f"使用使用者提供的服務帳號資訊初始化 GoogleDriveService 失敗 (ValueError): {e_drive} (持久模式)")
                        app_state["drive_service"] = None
                        app_state["report_ingestion_service"] = None
                        app_state["drive_service_status"] = f"初始化錯誤 (使用者提供的SA)：無效的憑證 ({e_drive}, 持久模式)"
                        app_state["critical_config_missing_sa_credentials"] = True
                    except Exception as e_drive_other:
                        logger.error(f"使用使用者提供的服務帳號資訊初始化 GoogleDriveService 時發生未預期錯誤: {e_drive_other} (持久模式)", exc_info=True)
                        app_state["drive_service"] = None
                        app_state["report_ingestion_service"] = None
                        app_state["drive_service_status"] = f"未預期的初始化錯誤 (使用者提供的SA): {str(e_drive_other)[:100]} (持久模式)"
                        app_state["critical_config_missing_sa_credentials"] = True
            except json.JSONDecodeError:
                logger.info("使用者提供的 API 金鑰不是 JSON 格式。將其視為普通 API 金鑰，不影響 Drive 服務憑證 (持久模式)。")
        else: # 持久模式，但 Drive 服務憑證已從環境加載且有效
            logger.info("持久模式下，Google Drive 服務帳號已從環境變數設定或先前已由使用者有效設定。此次提供的金鑰將僅用作 COLAB_GOOGLE_API_KEY。")
    else: # transient mode
        logger.info("暫存模式：使用者提供的 API 金鑰將被設定為 COLAB_GOOGLE_API_KEY。不會用於初始化 Google Drive 相關服務。")
        # 在暫存模式下，即使提供了看起來像服務帳號的 JSON，也不會去初始化 DriveService 或排程器。
        # critical_config_missing_sa_credentials 和 drive_service_status 應保持其暫存模式的狀態。
        app_state["drive_service_status"] = "暫存模式下未啟用"
        app_state["critical_config_missing_sa_credentials"] = False # 在暫存模式下，SA憑證不被視為"缺失"（因為不需要）


    final_sa_loaded_and_functional = False
    if operation_mode == "persistent":
        final_sa_loaded_and_functional = not app_state.get("critical_config_missing_sa_credentials", False) and \
                                         app_state.get("drive_service") is not None

    return ApiKeyStatusResponse(
        is_set=True,
        source="使用者提供",
        drive_service_account_loaded=final_sa_loaded_and_functional
    )

if __name__ == "__main__":
    # 為了本地開發方便，可以設定一些預設環境變數
    # 注意：這些僅在直接執行 main.py 時有效 (即 `python main.py`)
    # 如果使用 uvicorn main:app，則需要在環境中設定這些變數
    os.environ.setdefault("REPORTS_DB_FILENAME", "dev_reports.sqlite") # 開發用報告資料庫檔案名
    os.environ.setdefault("PROMPTS_DB_FILENAME", "dev_prompts.sqlite") # 開發用提示詞資料庫檔案名
    os.environ.setdefault("SCHEDULER_INTERVAL_MINUTES", "1") # 開發時使用較短的排程間隔，例如1分鐘
    # 以下為選填的開發用環境變數，若有需要可取消註解並設定適當值：
    # logger.info("提示：若需測試排程器與 Google Drive 整合，請設定 WOLF_IN_FOLDER_ID, WOLF_PROCESSED_FOLDER_ID 及服務帳號憑證。")
    # os.environ.setdefault("WOLF_IN_FOLDER_ID", "your_dev_wolf_in_folder_id_here")
    # os.environ.setdefault("WOLF_PROCESSED_FOLDER_ID", "your_dev_wolf_processed_folder_id_here")
    # 若使用 GOOGLE_APPLICATION_CREDENTIALS:
    # os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", "path/to/your/dev-service-account-file.json")
    # 若使用 GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT (注意 JSON 字串的引號和逸出):
    # os.environ.setdefault("GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT", '{"type": "service_account", ...}')

    logger.info("啟動 FastAPI 開發伺服器 (透過 __main__ 直接執行)...")
    port = int(os.getenv("PORT", 8000)) # 從環境變數讀取 PORT，預設 8000
    host = os.getenv("HOST", "0.0.0.0") # 從環境變數讀取 HOST，預設 "0.0.0.0" (監聽所有網路介面)

    # 注意: 在 __main__ 中直接執行時，uvicorn.run(app, ...) 比 uvicorn.run("main:app", ...) 更標準且推薦
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")

# 更新 FastAPI 應用程式的標題、描述和 OpenAPI tags
app.title = "蒼狼 AI V2.2 後端服務"
app.description = "用於蒼狼 AI 可觀測性分析平台 V2.2 的後端 API 服務。提供數據處理、AI 分析排程、組態設定及狀態查詢等功能。"
app.version = "2.2.1" # 版本號可依據實際修改情況更新

app.openapi_tags = [
    {
        "name": "General", # 維持英文以供潛在的自動化工具識別，但描述改為中文
        "description": "通用接口，例如健康檢查、API 版本資訊等。",
    },
    {
        "name": "設定", # 原 "Configuration"
        "description": "應用程式組態設定相關接口，例如 API 金鑰管理、服務帳號設定等。",
    },
    # 可以根據 API 的實際結構添加更多中文標籤和描述
    # 例如:
    # {
    #     "name": "資料管理",
    #     "description": "與資料庫互動、報告存取相關的接口。",
    # },
    # {
    #     "name": "排程控制",
    #     "description": "排程任務狀態查詢與手動觸發等相關接口。",
    # }
]
