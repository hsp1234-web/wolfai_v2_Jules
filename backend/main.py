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
    "google_api_key": None, # 通用 AI 服務 API 金鑰 (例如 Gemini)
    "google_api_key_source": None, # API 金鑰的來源 (例如 "environment", "使用者提供")
    "service_account_info": None, # Google Drive 服務帳號的 JSON 憑證內容
    "drive_service": None, # GoogleDriveService 的實例
    "dal": None, # DataAccessLayer 的實例
    "report_ingestion_service": None, # ReportIngestionService 的實例
    "scheduler": None, # APScheduler 的實例
    "reports_db_path": None, # 報告資料庫的檔案路徑
    "prompts_db_path": None, # 提示詞資料庫的檔案路徑
    "operation_mode": "transient", # 操作模式，預設為 "transient" (暫存)
    "drive_service_status": "未初始化", # Google Drive 服務的詳細狀態
    "critical_config_missing_drive_folders": False, # 狀態標記：是否缺少必要的 Google Drive 資料夾 ID
    "critical_config_missing_sa_credentials": False, # 狀態標記：是否缺少 Google Drive 服務帳號憑證
}

class ApiKeyRequest(BaseModel):
    api_key: str

class HealthCheckResponse(BaseModel):
    status: str = "OK"
    message: str = "API 正常運行" # 繁體中文
    scheduler_status: str = "未初始化" # 繁體中文
    drive_service_status: str = "未初始化" # 繁體中文
    config_status: str = "檢查中..." # 繁體中文，用於更詳細的配置狀態
    mode: str # 新增欄位: 當前操作模式 (例如 "transient" 或 "persistent")

class ApiKeyStatusResponse(BaseModel):
    is_set: bool # AI 服務 API 金鑰是否已設定
    source: Optional[str] = None # API 金鑰的來源
    drive_service_account_loaded: bool = False # Google Drive 服務帳號是否已成功加載且可用 (僅持久模式下有意義)

app = FastAPI(
    title="蒼狼 AI V2.2 後端服務", # 更新為 V2.2
    description="用於蒼狼 AI 可觀測性分析平台 V2.2 的後端 API 服務。提供數據處理、AI 分析排程、組態設定及狀態查詢等功能。", # 更新為 V2.2
    version="2.2.0" # 更新為 V2.2
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
    app_state["operation_mode"] = operation_mode

    # 1. 加載環境變數和配置
    env_api_key = os.getenv("COLAB_GOOGLE_API_KEY")
    if env_api_key:
        app_state["google_api_key"] = env_api_key
        app_state["google_api_key_source"] = "environment" # 記錄金鑰來源為環境變數
        logger.info("AI 服務 API 金鑰 (COLAB_GOOGLE_API_KEY) 已從環境變數成功加載。")
    else:
        logger.warning("環境變數中未找到 AI 服務 API 金鑰 (COLAB_GOOGLE_API_KEY)。若要使用 AI 分析功能，可能需要使用者透過 API 設定。")
        # 注意：此時 app_state["google_api_key"] 保持為 None

    service_account_json_content = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT")
    service_account_file_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    if service_account_json_content:
        try:
            app_state["service_account_info"] = json.loads(service_account_json_content)
            logger.info("Google Drive 服務帳號憑證已從 GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT 環境變數成功加載。")
        except json.JSONDecodeError as e:
            logger.error(f"解析 GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT 環境變數失敗: {e}。")
            app_state["critical_config_missing_sa_credentials"] = True # 標記服務帳號憑證缺失
    elif service_account_file_path:
        if os.path.exists(service_account_file_path):
            try:
                with open(service_account_file_path, 'r') as f:
                    app_state["service_account_info"] = json.load(f)
                logger.info(f"Google Drive 服務帳號憑證已從檔案 {service_account_file_path} (GOOGLE_APPLICATION_CREDENTIALS) 成功加載。")
            except Exception as e:
                logger.error(f"從檔案 {service_account_file_path} 加載 Google Drive 服務帳號憑證失敗: {e}。")
                app_state["critical_config_missing_sa_credentials"] = True # 標記服務帳號憑證缺失
        else:
            logger.warning(f"GOOGLE_APPLICATION_CREDENTIALS 環境變數指向的檔案 {service_account_file_path} 不存在。")
            app_state["critical_config_missing_sa_credentials"] = True # 標記服務帳號憑證缺失
    else:
        # 若兩種方式都未提供服務帳號憑證
        logger.warning("未提供 Google Drive 服務帳號憑證 (既未設定 GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT 也未設定 GOOGLE_APPLICATION_CREDENTIALS)。")
        app_state["critical_config_missing_sa_credentials"] = True # 標記服務帳號憑證缺失

    # 根據是否成功加載服務帳號資訊來更新 drive_service_status 的初始狀態
    if app_state["critical_config_missing_sa_credentials"]:
        app_state["drive_service_status"] = "錯誤：Google 服務帳號憑證未設定或加載失敗"
    elif not app_state.get("service_account_info"): # 雙重檢查，理論上 critical_config_missing_sa_credentials 已涵蓋
        app_state["drive_service_status"] = "錯誤：Google 服務帳號憑證內容為空"
        app_state["critical_config_missing_sa_credentials"] = True


    # 檢查必要的 Drive Folder ID (僅在持久模式下對功能至關重要，但任何模式下都檢查以提供反饋)
    wolf_in_folder_id_env = os.getenv("WOLF_IN_FOLDER_ID")
    wolf_processed_folder_id_env = os.getenv("WOLF_PROCESSED_FOLDER_ID")
    if not wolf_in_folder_id_env or not wolf_processed_folder_id_env:
        logger.warning("警告：必要的 Google Drive 資料夾 ID (WOLF_IN_FOLDER_ID 或 WOLF_PROCESSED_FOLDER_ID) 未完整設定。")
        app_state["critical_config_missing_drive_folders"] = True # 標記 Drive Folder ID 缺失
    else:
        logger.info("Google Drive 資料夾 ID (WOLF_IN_FOLDER_ID, WOLF_PROCESSED_FOLDER_ID) 已從環境變數讀取。")

    # 資料庫路徑設定
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(backend_dir)
    base_data_path = os.path.join(project_root, 'data') # Colab 環境中，此 data 目錄會在 /content/wolf_project/wolfAI_v1/data
    os.makedirs(base_data_path, exist_ok=True) # 確保 data 目錄存在

    reports_db_env_path = os.getenv('REPORTS_DB_PATH') # 由 Colab 筆記本根據操作模式設定
    prompts_db_env_path = os.getenv('PROMPTS_DB_PATH') # 由 Colab 筆記本根據操作模式設定

    # 如果 REPORTS_DB_PATH 或 PROMPTS_DB_PATH 未被 Colab 筆記本設定 (例如本地開發)，則使用預設檔名在 base_data_path 下
    reports_db_filename = os.getenv("REPORTS_DB_FILENAME", "reports.sqlite")
    prompts_db_filename = os.getenv("PROMPTS_DB_FILENAME", "prompts.sqlite")

    app_state["reports_db_path"] = reports_db_env_path if reports_db_env_path else os.path.join(base_data_path, reports_db_filename)
    app_state["prompts_db_path"] = prompts_db_env_path if prompts_db_env_path else os.path.join(base_data_path, prompts_db_filename)

    logger.info(f"報告資料庫路徑設定為: {app_state['reports_db_path']}")
    logger.info(f"提示詞資料庫路徑設定為: {app_state['prompts_db_path']}")

    # 2. 初始化服務 (DataAccessLayer 在所有模式下都初始化)
    app_state["dal"] = DataAccessLayer(
        reports_db_path=app_state["reports_db_path"],
        prompts_db_path=app_state["prompts_db_path"]
    )
    await app_state["dal"].initialize_databases()
    logger.info("DataAccessLayer 已初始化並檢查/創建了資料庫表。")

    # 根據操作模式，決定是否初始化 Google Drive 相關的服務
    if operation_mode == "persistent":
        logger.info("持久模式：嘗試初始化 Google Drive 相關服務...")
        if not app_state["critical_config_missing_sa_credentials"] and app_state.get("service_account_info"):
            try:
                app_state["drive_service"] = GoogleDriveService(
                    service_account_info=app_state.get("service_account_info")
                )
                logger.info("GoogleDriveService 已成功初始化 (持久模式)。")
                app_state["drive_service_status"] = "已初始化 (持久模式)"
            except Exception as e:
                logger.error(f"GoogleDriveService 初始化失敗 (持久模式): {e}", exc_info=True)
                app_state["drive_service"] = None
                app_state["drive_service_status"] = f"初始化錯誤 (持久模式): {str(e)[:100]}"
        else:
            logger.warning("由於 Google 服務帳號憑證缺失或無效，GoogleDriveService 未初始化 (持久模式)。")
            # drive_service_status 已在前面憑證檢查部分設定

        if app_state.get("drive_service") and app_state.get("dal"):
            app_state["report_ingestion_service"] = ReportIngestionService(
                drive_service=app_state["drive_service"],
                dal=app_state["dal"]
            )
            logger.info("ReportIngestionService 已初始化 (持久模式)。")
        else:
            logger.warning("由於 GoogleDriveService 或 DataAccessLayer 未成功初始化，ReportIngestionService 未初始化 (持久模式)。")

        if app_state.get("report_ingestion_service") and not app_state["critical_config_missing_drive_folders"]:
            scheduler_interval_minutes = int(get_env_or_default("SCHEDULER_INTERVAL_MINUTES", "15"))
            scheduler = AsyncIOScheduler(timezone="UTC")
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
                logger.error(f"APScheduler 排程器啟動失敗 (持久模式): {e}", exc_info=True)
        elif app_state["critical_config_missing_drive_folders"]:
            logger.warning("排程器未啟動 (持久模式)：由於 Google Drive 資料夾 ID 未完整設定。")
        else:
            logger.warning("排程器未啟動 (持久模式)：由於 ReportIngestionService 未初始化。")
    else: # transient mode
        logger.info("暫存模式：跳過 GoogleDriveService, ReportIngestionService, 和 APScheduler 的初始化。")
        app_state["drive_service_status"] = "暫存模式下未啟用" # 明確狀態

    logger.info("後端應用程式啟動流程完成。")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("後端應用程式正在關閉...")
    scheduler = app_state.get("scheduler")
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False) # 關閉排程器，不等待當前任務完成
        logger.info("APScheduler 排程器已成功關閉。")
    logger.info("後端應用程式已成功關閉。")

@app.get("/api/health", response_model=HealthCheckResponse, tags=["General"])
async def health_check():
    # 從 app_state 獲取相關狀態
    operation_mode = app_state.get("operation_mode", "未知")
    scheduler = app_state.get("scheduler")
    current_drive_status = app_state.get("drive_service_status", f"未知狀態 (模式: {operation_mode})")

    # 設定排程器狀態訊息
    scheduler_status_msg = f"未設定或未執行 (模式: {operation_mode})"
    if operation_mode == "persistent":
        if scheduler and scheduler.running:
            job = scheduler.get_job("report_ingestion_job")
            next_run = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S %Z') if job and job.next_run_time else "未知"
            scheduler_status_msg = f"執行中 (模式: persistent, 下次執行: {next_run})"
        elif app_state.get("report_ingestion_service") and not app_state.get("critical_config_missing_drive_folders"):
             scheduler_status_msg = "已配置但啟動失敗或已關閉 (模式: persistent)"
        elif app_state.get("critical_config_missing_drive_folders"):
            scheduler_status_msg = "未啟動 (模式: persistent, Google Drive 資料夾 ID 未完整設定)"
        else:
             scheduler_status_msg = f"未啟動 (模式: persistent, ReportIngestionService 未初始化或未知原因)"
    else: # transient mode
        scheduler_status_msg = "暫存模式下未啟用"

    # 收集設定相關的訊息
    config_messages = []
    # 檢查 AI API 金鑰 (所有模式下都檢查)
    if not app_state.get("google_api_key"):
        config_messages.append("警告：Google AI API 金鑰 (COLAB_GOOGLE_API_KEY) 未設定，AI 功能將受限。")

    # 持久模式下的特定檢查
    if operation_mode == "persistent":
        if app_state.get("critical_config_missing_sa_credentials"):
            config_messages.append("錯誤：Google 服務帳號憑證未設定或加載失敗。")
        if app_state.get("critical_config_missing_drive_folders"):
            config_messages.append("錯誤：Google Drive 資料夾 ID (WOLF_IN_FOLDER_ID 或 WOLF_PROCESSED_FOLDER_ID) 未設定。")

        # 如果 Drive Service 狀態明確指出錯誤，且與上述錯誤不重複，則加入
        # 例如，憑證格式錯誤，或初始化時的其他錯誤
        is_sa_credential_error_already_reported = app_state.get("critical_config_missing_sa_credentials") and \
                                                 ("憑證" in current_drive_status or "credential" in current_drive_status.lower())
        if ("錯誤" in current_drive_status or "Error" in current_drive_status or "失敗" in current_drive_status) and \
           not is_sa_credential_error_already_reported and \
           current_drive_status != "錯誤：Google 服務帳號憑證未設定或加載失敗": # 避免與上面 generic sa error 重複
            config_messages.append(f"Google Drive 服務: {current_drive_status}")


    # 組合最終的設定狀態訊息
    if not config_messages:
        final_config_status = "設定檔檢查通過" # 繁體中文
    else:
        final_config_status = " | ".join(config_messages)
        # 如果有錯誤訊息，且Drive Service狀態良好，但前面沒有加入Drive Service狀態，這裡可以考慮加入一個正面的Drive Service狀態
        if operation_mode == "persistent" and "錯誤" not in final_config_status and \
           current_drive_status == "已初始化 (持久模式)" and "Google Drive 服務" not in final_config_status:
            # 確保不在已有錯誤的情況下添加 "已初始化"
             pass # 或者可以選擇性添加，但目前邏輯是只報問題或全部通過


    return HealthCheckResponse(
        scheduler_status=scheduler_status_msg,
        drive_service_status=current_drive_status, # 直接使用 startup 或 set_api_key 設定的 drive_service_status
        config_status=final_config_status,
        mode=operation_mode
    )

@app.get("/api/get_api_key_status", response_model=ApiKeyStatusResponse, tags=["設定"])
async def get_api_key_status():
    api_key_is_set = bool(app_state.get("google_api_key"))
    api_key_source = app_state.get("google_api_key_source", "未設定")
    operation_mode = app_state.get("operation_mode", "未知")

    sa_loaded_and_functional = False
    if operation_mode == "persistent":
        sa_loaded_and_functional = not app_state.get("critical_config_missing_sa_credentials", False) and \
                                   app_state.get("drive_service") is not None

    return ApiKeyStatusResponse(
        is_set=api_key_is_set,
        source=api_key_source,
        drive_service_account_loaded=sa_loaded_and_functional
    )

@app.post("/api/set_api_key", response_model=ApiKeyStatusResponse, tags=["設定"])
async def set_api_key(payload: ApiKeyRequest):
    if not payload.api_key:
        raise HTTPException(status_code=400, detail="API 金鑰不能為空") # 繁體中文

    key_to_set = payload.api_key
    app_state["google_api_key"] = key_to_set
    app_state["google_api_key_source"] = "使用者提供" # 繁體中文
    logger.info("AI 服務 API 金鑰 (COLAB_GOOGLE_API_KEY) 已由使用者透過 API 設定。")
    operation_mode = app_state.get("operation_mode", "transient")

    if operation_mode == "persistent":
        # 只有在持久模式下，才嘗試將使用者提供的金鑰用於 Drive 服務
        if app_state.get("critical_config_missing_sa_credentials", True) or not app_state.get("service_account_info"):
            try:
                key_json = json.loads(key_to_set)
                if isinstance(key_json, dict) and key_json.get("type") == "service_account":
                    logger.info("使用者提供的 API 金鑰被識別為服務帳號 JSON。嘗試用於 Google Drive 服務 (持久模式)...")
                    app_state["service_account_info"] = key_json
                    app_state["critical_config_missing_sa_credentials"] = False # 重設憑證缺失標記

                    # 清理並重新初始化 DriveService 及相關服務
                    if app_state.get("scheduler") and app_state["scheduler"].running:
                        app_state["scheduler"].shutdown(wait=False)
                        app_state["scheduler"] = None
                        logger.info("已關閉並移除現有排程器 (持久模式)，準備使用新憑證重啟。")
                    app_state["drive_service"] = None # 清除舊實例
                    app_state["report_ingestion_service"] = None # 清除舊實例

                    try:
                        app_state["drive_service"] = GoogleDriveService(service_account_info=key_json)
                        logger.info("GoogleDriveService 已使用使用者提供的服務帳號資訊成功初始化 (持久模式)。")
                        app_state["drive_service_status"] = "已初始化 (使用者提供的服務帳號, 持久模式)" # 繁體中文

                        if app_state.get("dal"):
                            app_state["report_ingestion_service"] = ReportIngestionService(
                                drive_service=app_state["drive_service"],
                                dal=app_state["dal"]
                            )
                            logger.info("ReportIngestionService 已使用新的 DriveService 實例更新/初始化 (持久模式)。")

                            if not app_state["critical_config_missing_drive_folders"]:
                                scheduler_interval_minutes = int(get_env_or_default("SCHEDULER_INTERVAL_MINUTES", "15"))
                                new_scheduler = AsyncIOScheduler(timezone="UTC")
                                new_scheduler.add_job(
                                    trigger_report_ingestion_task,
                                    trigger=IntervalTrigger(minutes=scheduler_interval_minutes),
                                    args=[app_state["report_ingestion_service"]],
                                    id="report_ingestion_job",
                                    name="定期從 Google Drive 擷取報告 (使用者提供SA後, 持久模式)", # 繁體中文
                                    replace_existing=True
                                )
                                try:
                                    new_scheduler.start()
                                    app_state["scheduler"] = new_scheduler
                                    logger.info(f"APScheduler (使用者提供SA後, 持久模式) 已啟動，每隔 {scheduler_interval_minutes} 分鐘執行。")
                                except Exception as e_sched:
                                    logger.error(f"APScheduler (使用者提供SA後, 持久模式) 啟動失敗: {e_sched}", exc_info=True)
                        else:
                            logger.warning("DataAccessLayer 未初始化，ReportIngestionService 無法配置 (持久模式)。")
                    except Exception as e_drive:
                        logger.error(f"使用使用者提供的服務帳號資訊初始化 GoogleDriveService 失敗 (持久模式): {e_drive}", exc_info=True)
                        app_state["drive_service"] = None
                        app_state["report_ingestion_service"] = None
                        app_state["drive_service_status"] = f"初始化錯誤 (使用者提供的SA)：{str(e_drive)[:100]} (持久模式)" # 繁體中文
                        app_state["critical_config_missing_sa_credentials"] = True
            except json.JSONDecodeError:
                logger.info("使用者提供的 API 金鑰不是 JSON 格式。將其視為普通 AI API 金鑰，不影響 Drive 服務憑證 (持久模式)。") # 繁體中文
        else:
            logger.info("持久模式下，Google Drive 服務帳號已從環境變數設定或先前已由使用者有效設定。此次提供的金鑰將僅用作 AI 服務 API 金鑰。") # 繁體中文
    else: # transient mode
        logger.info("暫存模式：使用者提供的 API 金鑰將被設定為 AI 服務 API 金鑰。不會用於初始化 Google Drive 相關服務。") # 繁體中文
        app_state["drive_service_status"] = "暫存模式下未啟用"
        app_state["critical_config_missing_sa_credentials"] = False

    final_sa_loaded_and_functional = False
    if operation_mode == "persistent":
        final_sa_loaded_and_functional = not app_state.get("critical_config_missing_sa_credentials", False) and \
                                         app_state.get("drive_service") is not None

    return ApiKeyStatusResponse(
        is_set=True,
        source="使用者提供", # 繁體中文
        drive_service_account_loaded=final_sa_loaded_and_functional
    )

if __name__ == "__main__":
    os.environ.setdefault("REPORTS_DB_FILENAME", "dev_reports.sqlite")
    os.environ.setdefault("PROMPTS_DB_FILENAME", "dev_prompts.sqlite")
    os.environ.setdefault("SCHEDULER_INTERVAL_MINUTES", "1")
    # logger.info("提示：若需測試排程器與 Google Drive 整合，請設定 WOLF_IN_FOLDER_ID, WOLF_PROCESSED_FOLDER_ID 及服務帳號憑證。") # 繁體中文
    logger.info("啟動 FastAPI 開發伺服器 (透過 __main__ 直接執行)...") # 繁體中文
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")

    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")

app.title = "蒼狼 AI V2.2 後端服務"
app.description = "用於蒼狼 AI 可觀測性分析平台 V2.2 的後端 API 服務。提供數據處理、AI 分析排程、組態設定及狀態查詢等功能。"
app.version = "2.2.1" # 假設因本次修改而更新了小版本

app.openapi_tags = [
    {
        "name": "General",
        "description": "通用接口，例如健康檢查、API 版本資訊等。", # 繁體中文
    },
    {
        "name": "設定",
        "description": "應用程式組態設定相關接口，例如 API 金鑰管理等。", # 繁體中文 (簡化了原描述，因為服務帳號設定已整合)
    },
]
