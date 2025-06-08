# Wolf AI 可觀測性分析平台 - V2.2

[![在 Colab 中開啟](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/hsp1234-web/wolfai_v2_2/blob/main/run_in_colab.ipynb)

## 專案摘要

Wolf AI V2.2 是一個旨在幫助使用者深入分析、總結並問答各類報告內容（初期以週報為主）的 AI 對話系統。此版本從靜態檔案系統架構全面升級，以 Google Drive 為後盾、雙 SQLite 資料庫為核心，實現動態資料管理。前端採用 Google Material Design 3 (M3) 設計語言，透過卡片式的引導流程優化使用者體驗。後端遵循全面異步、高內聚、低耦合的模組化原則設計。專案以 Google Colab 為核心部署環境，整合其原生功能，實現一鍵啟動。

## 主要功能

*   **上下文理解的 AI 對話**: 與 AI 進行多輪對話，分析報告內容。
*   **動態報告匯入**: 支援從 Google Drive `wolf_in` 資料夾自動擷取新報告，或透過網頁上傳。
*   **引導式使用者體驗**: 卡片式流程（設定 -> 選擇檔案 -> 互動對話 -> 產出報告）。
*   **Google Drive 整合**:
    *   核心資料庫 (`reports.sqlite`, `prompts.sqlite`) 存儲於使用者 Drive。
    *   報告在 Drive 中的指定資料夾 (`wolf_in`, `wolf_in/processed`) 管理。
    *   支援資料庫備份與還原 (透過 Drive 操作)。
*   **金鑰管理**: 優先從 Colab 環境密鑰讀取 API 金鑰，若無則引導使用者輸入。
*   **Colab 一鍵部署**: 透過 `run_in_colab.ipynb` 筆記本快速啟動完整應用。

## 技術棧

### 後端
*   **框架**: FastAPI
*   **語言**: Python
*   **資料庫**: SQLite (透過 `aiosqlite` 進行異步操作)
*   **雲端儲存**: Google Drive API (透過 `aiogoogle` 和 `google-api-python-client`)
*   **背景任務**: APScheduler
*   **主要依賴**: `fastapi`, `uvicorn`, `aiosqlite`, `APScheduler`, `google-api-python-client`, `aiogoogle`

### 前端
*   **框架**: Next.js (React)
*   **語言**: TypeScript
*   **UI 元件庫**: MUI (Material-UI) - 實現 Google Material Design 3 風格
*   **主要依賴**: `next@13.5.6`, `react@18`, `react-dom@18`, `@mui/material@5.14.20`, `@emotion/react@11.11.0`, `@emotion/styled@11.11.0`

### 部署
*   **核心環境**: Google Colaboratory (`.ipynb` 筆記本)
*   **版本控制**: Git & GitHub (或類似平台)

## 如何啟動 (使用 Colab)

點擊本文件最上方的 "Open in Colab" 徽章即可在 Google Colaboratory 環境中開啟 `run_in_colab.ipynb` 筆記本。打開後，請依照筆記本內的儲存格說明逐步執行。以下為主要步驟概覽：

### Colab-步驟一：環境設定與授權

此步驟在 Colab 筆記本中執行，主要完成以下任務：

1.  **掛載 Google Drive**:
    *   筆記本的第一個程式碼儲存格會提示您授權 Colab 存取您的 Google Drive。這是必要的，因為專案的資料庫檔案 (`reports.sqlite`, `prompts.sqlite`) 以及後續處理的報告檔案都將儲存在您的 Drive 中，實現資料持久化。
2.  **設定 Google API 金鑰與服務帳號憑證**:
    *   為了讓應用程式能夠順利使用 Google 的 AI 服務 (例如 Gemini API) 以及存取 Google Drive，您需要提供必要的憑證。筆記本提供了幾種設定方式：
        *   **方式一 (推薦用於 Google Drive API)**: 上傳您的 Google Cloud 服務帳號金鑰 JSON 檔案。
            *   將您的服務帳號 JSON 金鑰檔案重新命名為 `service_account.json`。
            *   執行筆記本中第一步的程式碼儲存格時，它會提供一個上傳按鈕。點擊「選擇檔案」並上傳您準備好的 `service_account.json`。
            *   此檔案將被複製到 Colab 環境中，筆記本會自動設定 `GOOGLE_APPLICATION_CREDENTIALS` 環境變數指向此檔案，供後端服務使用。
        *   **方式二 (用於 Gemini 等 Google AI 服務 API 金鑰)**: 在 Colab 的「密鑰 (Secrets)」管理器中設定您的 API 金鑰。
            *   在 Colab 介面，點擊左側工具列的「鑰匙」圖示，進入密鑰管理器。
            *   點擊「新增密鑰」。
            *   將密鑰的**名稱**精確設定為 `COLAB_GOOGLE_API_KEY` (後端程式會讀取此環境變數名稱)。
            *   將您的實際 API 金鑰內容貼入**值 (Value)** 的欄位中。
            *   確保「允許筆記本存取 (Notebook access)」的開關已啟用。
        *   **方式三 (備選，用於 Google Drive 服務帳號 JSON 內容)**: 如果您不方便上傳檔案，也可以直接將服務帳號 JSON 的**完整內容**作為字串貼入 Colab 的「密鑰 (Secrets)」管理器。
            *   密鑰**名稱**：`GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT`
            *   **值 (Value)**：貼上您的服務帳號 JSON 的**全部內容**。
    *   **重要安全性提示**: 您的 API 金鑰和服務帳號憑證極為敏感，請務必妥善保管，不要直接寫在程式碼或筆記本中。Colab 的密鑰管理器提供了一種在執行環境中相對安全地使用這些敏感資訊的方式。

### Colab-步驟二：複製專案程式碼與安裝依賴

此步驟的程式碼儲存格將執行以下操作：

1.  **定義專案來源**:
    *   筆記本中會預設一個 `GIT_REPO_URL` 變數，指向本專案的 GitHub 倉庫。如果您是從自己的 fork 或不同分支執行，請務必修改此 URL 為正確的倉庫地址。
2.  **複製專案**:
    *   使用 `git clone` 指令從指定的 URL 將最新的專案程式碼下載到 Colab 的執行環境中 (通常位於 `/content/wolf_project/wolf_ai_v2_2` 路徑下)。
    *   為了確保每次都是全新的部署，程式碼會先嘗試移除可能已存在的舊專案資料夾。
3.  **安裝後端依賴**:
    *   讀取 `backend/requirements.txt` 檔案，使用 `pip install -r` 命令安裝所有後端 Python 套件。此過程可能需要數分鐘。
4.  **安裝前端依賴**:
    *   進入 `frontend/` 目錄，如果存在 `package.json`，則使用 `npm ci --verbose` (或 `npm install --verbose`) 命令安裝所有前端 JavaScript/TypeScript 套件。此過程也可能需要數分鐘。

### Colab-步驟三：準備 Google Drive 資料夾與資料庫檔案

為了讓應用程式能夠持久化儲存資料，此步驟將在您的 Google Drive 中建立必要的資料夾結構，並處理資料庫檔案。

1.  **目標資料夾結構** (將創建於您 Google Drive 的根目錄下，如果尚不存在):
    *   `wolf_AI_data/` (主資料夾，用於存放所有與本專案相關的資料)
        *   `wolf_in/` (此資料夾用於存放等待 AI 處理的原始報告檔案)
            *   `processed/` (此子資料夾用於存放已被 AI 成功處理過的報告檔案的歸檔位置)
2.  **資料夾創建與 ID 獲取**:
    *   筆記本中的程式碼會使用 Google Drive API 檢查上述資料夾是否存在，如果不存在，則會自動創建它們。
    *   成功創建或找到 `wolf_in` 和 `processed` 資料夾後，筆記本會打印出這兩個資料夾的 Google Drive **Folder ID**。
3.  **設定 Folder ID 至 Colab Secrets**:
    *   **此為手動步驟，非常重要！** 您需要將上一步輸出中顯示的 `WOLF_IN_FOLDER_ID` 和 `WOLF_PROCESSED_FOLDER_ID` 的值，手動添加到 Colab 的「密鑰 (Secrets)」管理器中。
        *   密鑰名稱：`WOLF_IN_FOLDER_ID`，值：對應的 Folder ID 字串。
        *   密鑰名稱：`WOLF_PROCESSED_FOLDER_ID`，值：對應的 Folder ID 字串。
    *   後端服務的排程器會使用這些 ID 來監控 `wolf_in` 資料夾中是否有新的報告需要處理。
4.  **資料庫檔案處理**:
    *   筆記本會檢查您的 Google Drive 根目錄下 `/wolf_AI_data/` 資料夾中是否已存在 `reports.sqlite` 和 `prompts.sqlite` 資料庫檔案。
    *   **如果存在**: 這些資料庫檔案將被下載並複製到 Colab 本地專案的 `backend/data/` 目錄下，供應用程式本次執行使用。這樣可以載入先前儲存的資料。
    *   **如果不存在**: 後端應用程式在首次啟動時，會在 Colab 本地專案的 `backend/data/` 目錄下自動創建新的、空的資料庫檔案。這些新的資料庫檔案**不會**在此步驟自動回傳到您的 Google Drive，但您可以考慮在 Colab 會話結束前手動將它們從 Colab 環境下載並上傳到 Drive 的 `/wolf_AI_data/` 以便下次使用。

### Colab-步驟四：啟動應用程式服務與健康度偵測

這是執行應用程式的最後一個主要步驟。

1.  **環境變數檢查 (新增)**:
    *   在正式啟動服務前，新增的程式碼儲存格會檢查必要的 Colab Secrets 是否已設定，包括 `COLAB_GOOGLE_API_KEY`, `WOLF_IN_FOLDER_ID`, `WOLF_PROCESSED_FOLDER_ID`, 以及 `GOOGLE_APPLICATION_CREDENTIALS` (或 `GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT`)。
    *   如果檢測到有缺失的密鑰，將打印中文警告訊息，提示使用者返回設定。
2.  **啟動後端服務**:
    *   使用 `nohup python main.py > backend.log 2>&1 &` 命令在背景啟動 FastAPI 後端伺服器。日誌會輸出到專案根目錄下的 `backend.log` 檔案。
    *   後端服務會監聽預設的 8000 端口。
3.  **啟動前端服務**:
    *   使用 `nohup npm run dev -- -p 3000 -H 0.0.0.0 > frontend.log 2>&1 &` 命令在背景啟動 Next.js 前端開發伺服器。日誌會輸出到專案根目錄下的 `frontend.log` 檔案。
    *   前端服務會監聽預設的 3000 端口。
4.  **健康度偵測**:
    *   筆記本會執行一個迴圈，定期向後端 `/api/health` 和前端根路徑 `/` 發送請求，以檢查兩個服務是否都已成功啟動並回應正常。
5.  **顯示訪問連結**:
    *   一旦兩個服務都回報健康，筆記本會嘗試獲取並以醒目格式（加粗或 HTML）打印由 Colab 提供的公開訪問網址。這個網址通常是 Colab 將本地監聽的端口（例如前端的 3000 端口）代理轉發到的一個 `googleusercontent.com` 子域名。
    *   您需要複製此連結並在新的瀏覽器分頁中打開，即可開始使用 Wolf AI V2.2 平台。

### 開始使用

當 Colab 筆記本的最後一個儲存格成功執行完畢，並且顯示出前端訪問網址後，您就可以點擊該網址開始與您的 Wolf AI 平台互動了。如果遇到任何問題，請檢查 Colab 儲存格的輸出以及 `backend.log` 和 `frontend.log` 檔案獲取詳細錯誤資訊。

## 專案結構 (概覽)

```
wolf_ai_v2_2/
├── backend/            # 後端 FastAPI 應用
│   ├── services/       # 核心服務模組 (Drive, DAL, Ingestion)
│   ├── main.py         # FastAPI 應用入口
│   ├── scheduler_tasks.py # 排程任務
│   └── requirements.txt
├── frontend/           # 前端 Next.js 應用
│   ├── app/            # Next.js App Router 頁面 (Next.js 13.5.6, no src/app)
│   ├── components/     # React 元件 (包括 MUI 設定)
│   ├── public/
│   ├── package.json
│   └── next.config.js
├── data/               # 本地資料庫快取 (Colab 環境中，從 Drive 同步)
├── scripts/            # (可選) 其他輔助腳本
├── run_in_colab.ipynb  # Colab 部署與啟動筆記本
└── README.md           # 本檔案
```

## 貢獻

(如果接受貢獻，請在此處添加指南)

## 授權條款

(請在此處註明您的專案授權，例如 MIT, Apache 2.0 等)
