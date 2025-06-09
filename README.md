# Wolf AI 可觀測性分析平台 - V2.2

[![在 Colab 中開啟](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/hsp1234-web/wolfAI_v1/blob/main/run_in_colab.ipynb)

## 專案摘要

Wolf AI V2.2 是一個旨在幫助使用者深入分析、總結並問答各類報告內容（初期以週報為主）的 AI 對話系統。此版本從靜態檔案系統架構全面升級，以 Google Drive 為後盾、雙 SQLite 資料庫為核心，實現動態資料管理。前端採用 Google Material Design 3 (M3) 設計語言，透過卡片式的引導流程優化使用者體驗。後端遵循全面異步、高內聚、低耦合的模組化原則設計。專案以 Google Colab 為核心部署環境，整合其原生功能，實現一鍵啟動。

## 主要功能

* **上下文理解的 AI 對話**: 與 AI 進行多輪對話，分析報告內容。
* **動態報告匯入**: 支援從 Google Drive `wolf_in` 資料夾自動擷取新報告，或透過網頁上傳。
* **引導式使用者體驗**: 卡片式流程（設定 -> 選擇檔案 -> 互動對話 -> 產出報告）。
* **Google Drive 整合**:
    * 核心資料庫 (`reports.sqlite`, `prompts.sqlite`) 存儲於使用者 Drive。
    * 報告在 Drive 中的指定資料夾 (`wolf_in`, `wolf_in/processed`) 管理。
    * 支援資料庫備份與還原 (透過 Drive 操作)。
* **金鑰管理**: 優先從 Colab 環境密鑰讀取 API 金鑰，若無則引導使用者輸入。
* **Colab 一鍵部署**: 透過 `run_in_colab.ipynb` 筆記本快速啟動完整應用。
* **雙操作模式**: 支援「暫存模式」（快速啟動，資料不落地）與「持久模式」（整合 Google Drive，資料永久保存）。

## 技術棧

### 後端
* **框架**: FastAPI
* **語言**: Python
* **資料庫**: SQLite (透過 `aiosqlite` 進行異步操作)
* **雲端儲存**: Google Drive API (透過 `aiogoogle` 和 `google-api-python-client`)
* **背景任務**: APScheduler
* **主要依賴**: `fastapi`, `uvicorn`, `aiosqlite`, `APScheduler`, `google-api-python-client`, `aiogoogle`

### 前端
* **框架**: Next.js (React)
* **語言**: TypeScript
* **UI 元件庫**: MUI (Material-UI) - 實現 Google Material Design 3 風格
* **主要依賴**: `next@13.5.6`, `react@18`, `react-dom@18`, `@mui/material@5.14.20`, `@emotion/react@11.11.0`, `@emotion/styled@11.11.0`

### 部署
* **核心環境**: Google Colaboratory (`.ipynb` 筆記本)
* **版本控制**: Git & GitHub (或類似平台)

## 如何啟動

### 方法一：使用 "Open in Colab" 徽章 (建議)

蒼狼 AI V1 採用了全新的「一鍵部署」流程，大幅簡化了在 Google Colaboratory 中的啟動過程。

1.  **點擊 "Open in Colab" 徽章**:
    * 點擊本文件最上方的 [![在 Colab 中開啟](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/hsp1234-web/wolfAI_v1/blob/main/run_in_colab.ipynb) 徽章，即可在 Colab 中打開 `run_in_colab.ipynb` 筆記本。

2.  **執行唯一的程式碼儲存格**:
    * 筆記本現在只包含一個主要的程式碼儲存格。依照儲存格內的中文提示，逐步執行即可完成所有設定與啟動。

3.  **選擇操作模式**:
    * 在執行儲存格的初期，您將看到一個「選擇操作模式」的下拉選單。您可以選擇：
        * **暫存模式 (transient)**：此模式為預設選項，無需 Google Drive 授權即可快速啟動應用程式。所有資料（如上傳的報告、資料庫）將僅儲存在當前的 Colab 會話中，會話結束後資料將會遺失。此模式適用於快速體驗或不需要資料保存的場景。
        * **持久模式 (persistent)**：此模式需要您授權 Colab 掛載您的 Google Drive，並設定相關的雲端儲存密鑰。所有資料將會儲存到您指定的 Google Drive 路徑，從而實現資料的永久保存和跨會話使用。
    * 請根據您的需求選擇合適的模式。如果選擇「持久模式」，請確保已正確設定後述的 Colab Secrets。
    * 執行筆記本時，可以指定程式碼分支，通常保持預設即可。

### 方法二：直接複製程式碼到 Colab

如果您無法使用 "Open in Colab" 徽章，或者偏好手動操作，您可以開啟一個新的 Colab 筆記本，並將以下完整的程式碼複製貼上到一個儲存格中執行。

**請注意：** 使用此方法前，您**仍然需要**手動在 Colab 的「密鑰」管理器中設定必要的金鑰，詳細說明請參考下一章節。

```python
#@title 蒼狼 AI V1 可觀測性分析平台 - Colab 一鍵啟動
#@markdown ## 1. 指定要部署的程式碼分支
#@markdown ---
#@markdown 請輸入要從 GitHub 下載的程式碼分支名稱。通常保持預設值即可。
#@markdown - **main**: 代表最穩定的官方發布版。
#@markdown - **feat/...**: 代表正在開發中的新功能版。
branch_name = "main" #@param {type:"string"}
print(f"將從 GitHub 的 '{branch_name}' 分支下載最新的程式碼。")

#@markdown ## 2. 選擇操作模式
#@markdown ---
#@markdown **暫存模式**：無需授權，快速啟動，但資料不會被保存。
#@markdown **持久模式**：需要授權掛載 Google Drive，以永久保存您的資料。
operation_mode = "transient" #@param ["transient", "persistent"]

#@markdown ## 3. 選擇啟動模式
#@markdown ---
#@markdown 請選擇應用程式的啟動模式：
MODE = "normal" #@param ["normal", "debug"]
#@markdown ---
print(f"您選擇的操作模式是：{operation_mode}")
print(f"您選擇的啟動模式是：{MODE}")

# --- 後續程式碼將自動執行，無需修改 ---

# 將使用者選擇的 OPERATION_MODE 設置為環境變數
import os
os.environ['OPERATION_MODE'] = operation_mode
print(f"環境變數 OPERATION_MODE 已設定為: {os.getenv('OPERATION_MODE')}")

# --- 初始化與環境設定 ---
print("INFO: 開始執行 Colab 啟動程序...")
import shutil
import time
import requests
from IPython.display import display, HTML

# --- 步驟 1: 掛載 Google Drive (持久模式下) ---
print("\nSTEP 1: 檢查是否需要掛載 Google Drive...")
if operation_mode == "persistent":
    print("INFO: 持久模式 - 開始掛載 Google Drive...")
    try:
        from google.colab import drive
        drive.mount('/content/drive')
        print("SUCCESS: Google Drive 已成功掛載到 /content/drive")
    except Exception as e:
        print(f"ERROR: 掛載 Google Drive 失敗: {e}")
        print("請檢查彈出視窗是否已正確授權，或手動執行左側「掛載 Drive」按鈕。")
        raise SystemExit("Google Drive 掛載失敗，請處理後重試。")
else:
    print("INFO: 暫存模式 - 跳過 Google Drive 掛載。")

# --- 步驟 2 & 3: Colab Secrets 設定引導與檢查 ---
print("\nSTEP 2 & 3: Colab Secrets 設定引導與檢查...")
print("請確保您已在 Colab 的「密鑰 (Secrets)」管理器中設定以下密鑰：")
print("1. COLAB_GOOGLE_API_KEY: 您的 Google AI 服務 API 金鑰 (例如 Gemini API)。")
print("2. GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT: 您的服務帳號金鑰 JSON 檔案的「內容」。(持久模式必需)")
print("3. WOLF_IN_FOLDER_ID: Google Drive「待處理報告」的資料夾 ID。(持久模式必需)")
print("4. WOLF_PROCESSED_FOLDER_ID: Google Drive「已處理報告」的資料夾 ID。(持久模式必需)")

all_secrets_ok = True
google_api_key_env = os.getenv('COLAB_GOOGLE_API_KEY')
if not google_api_key_env:
    print("  ⚠️ COLAB_GOOGLE_API_KEY 未設定。AI 分析功能可能無法使用。")
    if operation_mode == "persistent":
        print("  ❌ 持久模式下，COLAB_GOOGLE_API_KEY 未設定將導致錯誤!")
        all_secrets_ok = False
else:
    print("  ✅ COLAB_GOOGLE_API_KEY 已設定。")

if operation_mode == "persistent":
    print("\nINFO: 持久模式 - 檢查 Google Drive 相關 Colab Secrets...")
    secrets_to_check_persistent = ['GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT', 'WOLF_IN_FOLDER_ID', 'WOLF_PROCESSED_FOLDER_ID']
    missing_secrets_persistent = []
    for secret_name in secrets_to_check_persistent:
        if not os.getenv(secret_name):
            missing_secrets_persistent.append(secret_name)
            print(f"  ❌ {secret_name} 未設定或為空值！")
        else:
            print(f"  ✅ {secret_name} 已設定。")
    if missing_secrets_persistent:
        all_secrets_ok = False

    if os.getenv('WOLF_IN_FOLDER_ID') and os.getenv('WOLF_PROCESSED_FOLDER_ID'):
        drive_mounted_base_path = "/content/drive/MyDrive/wolf_AI_data"
        reports_db_file = os.getenv('REPORTS_DB_FILENAME', 'reports.sqlite')
        prompts_db_file = os.getenv('PROMPTS_DB_FILENAME', 'prompts.sqlite')
        os.environ['REPORTS_DB_PATH'] = os.path.join(drive_mounted_base_path, reports_db_file)
        os.environ['PROMPTS_DB_PATH'] = os.path.join(drive_mounted_base_path, prompts_db_file)
        print(f"環境變數 REPORTS_DB_PATH 已設定為 (持久模式): {os.getenv('REPORTS_DB_PATH')}")
    else:
        if not missing_secrets_persistent: # Avoid duplicate error messages
             print("ERROR: 持久模式下 WOLF_IN_FOLDER_ID 或 WOLF_PROCESSED_FOLDER_ID 未設定，無法配置資料庫路徑。")
        all_secrets_ok = False
else:
    print("\nINFO: 暫存模式 - 跳過 Google Drive 相關 Colab Secrets 的檢查。")
    project_parent_dir_for_db = "/content/wolf_project"
    project_name_for_db = "wolfAI_v1"
    base_data_path_for_db = os.path.join(project_parent_dir_for_db, project_name_for_db, 'data')
    reports_db_file_transient = os.getenv('REPORTS_DB_FILENAME', 'session_reports.sqlite')
    prompts_db_file_transient = os.getenv('PROMPTS_DB_FILENAME', 'session_prompts.sqlite')
    os.environ['REPORTS_DB_PATH'] = os.path.join(base_data_path_for_db, reports_db_file_transient)
    os.environ['PROMPTS_DB_PATH'] = os.path.join(base_data_path_for_db, prompts_db_file_transient)
    print(f"環境變數 REPORTS_DB_PATH 已設定為 (暫存模式): {os.getenv('REPORTS_DB_PATH')}")

if not all_secrets_ok:
    raise SystemExit("❌ 錯誤：必要的 Colab Secrets 設定不完整或不正確，無法繼續。")
else:
    print("\n✅ Colab Secrets 設定檢查完畢。")

# --- 步驟 4: 複製專案程式碼 ---
print("\nSTEP 4: 複製專案程式碼...")
GIT_REPO_URL = "https://github.com/hsp1234-web/wolfAI_v1.git"
PROJECT_PARENT_DIR = "/content/wolf_project"
PROJECT_DIR_NAME = "wolfAI_v1"
FULL_PROJECT_PATH = os.path.join(PROJECT_PARENT_DIR, PROJECT_DIR_NAME)

if os.path.exists(FULL_PROJECT_PATH):
    shutil.rmtree(FULL_PROJECT_PATH)
os.makedirs(PROJECT_PARENT_DIR, exist_ok=True)
clone_command = f"git clone --depth 1 -b {branch_name} {GIT_REPO_URL} {FULL_PROJECT_PATH}"
clone_status = os.system(clone_command)

if clone_status != 0 or not os.path.isdir(FULL_PROJECT_PATH):
    raise SystemExit(f"ERROR: 專案複製失敗。請檢查 URL ('{GIT_REPO_URL}') 和分支 ('{branch_name}')。")
else:
    print(f"SUCCESS: 專案已成功複製到 '{FULL_PROJECT_PATH}'。")
    if operation_mode == 'transient':
        path_for_transient_db_data = os.path.join(FULL_PROJECT_PATH, 'data')
        if not os.path.exists(path_for_transient_db_data):
            os.makedirs(path_for_transient_db_data)
            print(f"為暫存模式創建了資料目錄: {path_for_transient_db_data}")

    # --- 步驟 5: 執行啟動腳本 ---
    print("\nSTEP 5: 執行主控啟動腳本 scripts/start.sh...")
    start_script_path = os.path.join(FULL_PROJECT_PATH, 'scripts', 'start.sh')
    if os.path.exists(start_script_path):
        os.system(f"chmod +x {start_script_path}")
        start_script_command = f"{start_script_path} --mode={MODE}"
        exit_code = os.system(start_script_command)
        if exit_code != 0:
            print(f"ERROR: 啟動腳本執行失敗，返回碼: {exit_code}。請檢查日誌。")
    else:
        raise SystemExit(f"ERROR: 主控啟動腳本 {start_script_path} 未找到！")

    # --- 步驟 6: 健康檢查 ---
    print("\nSTEP 6: 健康度偵測 (Health Check) - 請耐心等待約 1-2 分鐘...")
    BACKEND_SERVICE_PORT = 8000
    FRONTEND_SERVICE_PORT = 3000
    max_wait_duration_seconds = 120
    check_interval_seconds = 10
    start_check_time = time.time()
    backend_service_ready, frontend_service_ready = False, False

    while time.time() - start_check_time < max_wait_duration_seconds:
        try:
            if not backend_service_ready and requests.get(f"http://localhost:{BACKEND_SERVICE_PORT}/api/health", timeout=5).status_code == 200:
                backend_service_ready = True
                print(f"[{time.strftime('%H:%M:%S')}] ✅ 後端服務 READY.")
        except requests.RequestException:
            print(f"[{time.strftime('%H:%M:%S')}] ⏳ 後端服務未就緒...")

        try:
            if not frontend_service_ready and requests.get(f"http://localhost:{FRONTEND_SERVICE_PORT}", timeout=5).status_code == 200:
                frontend_service_ready = True
                print(f"[{time.strftime('%H:%M:%S')}] ✅ 前端服務 READY.")
        except requests.RequestException:
            print(f"[{time.strftime('%H:%M:%S')}] ⏳ 前端服務未就緒...")

        if backend_service_ready and frontend_service_ready:
            print("\n🎉 太棒了！後端和前端服務均已成功啟動！")
            break

        if time.time() - start_check_time >= max_wait_duration_seconds:
            print("\n⏱️ 服務啟動或健康檢查超時。")
            break

        time.sleep(check_interval_seconds)

    # --- 步驟 7: 顯示結果 ---
    if backend_service_ready and frontend_service_ready:
        border = "="*70
        print(f"\n{border}")
        display(HTML("<h2>✅ 應用程式已就緒，可以開始使用了！</h2>"))
        print("🔗 前端應用程式訪問網址 (Colab Proxy URL):")
        print(f"   請在本儲存格的輸出區域上方尋找由 Colab 自動生成的、形如 https://*.googleusercontent.com/ 的公開連結。")
        print(f"{border}\n")
    else:
        print("\n❌ 很抱歉，一個或多個服務未能成功啟動。")
        print("   請仔細檢查上方的日誌輸出以了解詳細錯誤信息。")

print("\nINFO: Colab 啟動程序執行完畢。")
```

### 主要自動化步驟概覽

該程式碼儲存格將自動執行以下核心步驟：

* **操作模式選擇**: 如上所述，允許使用者選擇「暫存模式」或「持久模式」。後續步驟的行為（如 Drive 掛載、Secrets 檢查）將依此選擇而定。
* **Google Drive 掛載**: 如果選擇「持久模式」，則提示並協助您授權 Colab 存取您的 Google Drive。暫存模式下跳過此步驟。
* **Colab Secrets 設定引導與檢查**:
    * 引導您在 Colab 的「密鑰 (Secrets)」管理器中設定必要的金鑰。
    * `COLAB_GOOGLE_API_KEY` (用於 Google AI 服務)：建議在兩種模式下都設定。
    * `GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT` (用於 Google Drive 存取), `WOLF_IN_FOLDER_ID` (Drive 中存放待處理報告的資料夾 ID), `WOLF_PROCESSED_FOLDER_ID` (Drive 中存放已處理報告的資料夾 ID)：這些主要在「持久模式」下是必需的。
    * 在執行後續步驟前，腳本會根據所選操作模式檢查相應的 Secrets 是否均已設定，若有缺失則會提示並終止執行。
* **應用程式啟動模式選擇**: 您可以在儲存格內選擇應用程式後端和前端服務的啟動模式（`normal` 或 `debug`）。此選擇與操作模式（暫存/持久）是獨立的。
* **專案部署與服務啟動**:
    * 自動從 GitHub (`https://github.com/hsp1234-web/wolfAI_v1.git`) 複製最新的專案程式碼。
    * 執行位於專案中 `scripts/start.sh` 的主控啟動腳本。此腳本會：
        * 根據所選模式，安裝後端 Python 依賴和前端 Node.js 依賴。
        * 根據所選模式，啟動後端 FastAPI 服務和前端 Next.js 服務。在 `normal` 模式下，服務會在背景執行，並將日誌輸出到專案根目錄下的 `backend.log` 和 `frontend.log`；在 `debug` 模式下，服務日誌會直接輸出到 Colab 儲存格。
* **健康檢查與顯示結果**:
    * 在啟動服務後，腳本會執行健康檢查，確認後端和前端服務是否都已成功啟動並正常回應。
    * 成功後，會嘗試顯示由 Colab 提供的公開訪問網址，您可以點擊該網址開始使用蒼狼 AI 平台。

### Colab Secrets 的重要性

為了確保應用程式能夠順利運行並存取必要的雲端服務，請務必依照 Colab 筆記本內的引導，在「密鑰 (Secrets)」管理器中正確設定以下項目：

* **`COLAB_GOOGLE_API_KEY`**: 您的 Google AI 服務 API 金鑰。
    * **重要性**: 在「暫存模式」和「持久模式」下都**強烈建議設定**，以確保 AI 分析功能可用。如果未設定，AI 對話和分析將無法進行。
* **`GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT`**: 您的 Google Cloud 服務帳號金鑰的 JSON **內容** (需具備 Drive 存取權限)。
    * **重要性**: 主要在「**持久模式**」下**必需**。用於授權應用程式存取您的 Google Drive 以讀取報告、儲存資料庫等。
    * 在「暫存模式」下，此密鑰不是必需的，因為應用程式不會嘗試連接到 Google Drive。
* **`WOLF_IN_FOLDER_ID`**: Google Drive 中用於存放**待處理報告**的資料夾 ID。
    * **重要性**: 主要在「**持久模式**」下**必需**。指定應用程式從哪個 Drive 資料夾讀取新的報告檔案。
    * 在「暫存模式」下不是必需的。
* **`WOLF_PROCESSED_FOLDER_ID`**: Google Drive 中用於存放**已處理報告**的資料夾 ID。
    * **重要性**: 主要在「**持久模式**」下**必需**。指定已處理報告在 Drive 中的歸檔位置。
    * 在「暫存模式」下不是必需的。

**設定建議**：
* **持久模式**: 請務必完整設定上述所有四個密鑰。建議您在首次執行筆記本前，預先在自己的 Google Drive 中創建 `wolf_AI_data` 資料夾，並在其下創建 `wolf_in` 和 `wolf_in/processed` 子資料夾。然後將這些資料夾的 ID 填入 Colab Secrets。如果您的 Drive 中已有 `reports.sqlite` 和 `prompts.sqlite` 資料庫檔案，請將它們放置於 `wolf_AI_data` 目錄下，後端服務啟動時會嘗試使用它們。
* **暫存模式**: `COLAB_GOOGLE_API_KEY` 仍然是推薦設定的，以使用 AI 功能。其他三個 Drive 相關密鑰可以不設定。應用程式在此模式下會使用 Colab 本地的臨時儲存空間。

### 開始使用

當 Colab 筆記本的程式碼儲存格成功執行完畢，並且顯示出前端訪問網址後，您就可以點擊該網址開始與您的蒼狼 AI 平台互動了。如果遇到任何問題，請仔細檢查 Colab 儲存格的輸出日誌。

## 專案結構 (概覽)

```
wolfAI_v1/
├── scripts/
│   └── start.sh        # 主控啟動腳本
├── backend/            # 後端 FastAPI 應用
│   ├── services/       # 核心服務模組 (Drive, DAL, Ingestion)
│   ├── main.py         # FastAPI 應用入口
│   ├── scheduler_tasks.py # 排程任務
│   └── requirements.txt
├── frontend/           # 前端 Next.js 應用
│   ├── app/            # Next.js App Router 頁面
│   ├── components/     # React 元件
│   ├── public/
│   ├── package.json
│   └── next.config.js
├── data/               # 本地資料庫快取 (由後端服務管理，可選擇性從 Drive 同步)
├── run_in_colab.ipynb  # Colab 部署與啟動筆記本
└── README.md           # 本檔案
```

## 貢獻

(如果接受貢獻，請在此處添加指南)

## 授權條款

(請在此處註明您的專案授權，例如 MIT, Apache 2.0 等)
