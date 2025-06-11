<div align="center">

[![專案狀態](https://img.shields.io/badge/status-in_development-green.svg)](https://github.com/hsp1234-web/wolfAI_v1)
[![GitHub 最後提交](https://img.shields.io/github/last-commit/hsp1234-web/wolfAI_v1)](https://github.com/hsp1234-web/wolfAI_v1/commits/main)
[![開源授權](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![後端 CI/CD](https://github.com/hsp1234-web/wolfAI_v1/actions/workflows/ci.yml/badge.svg)](https://github.com/hsp1234-web/wolfAI_v1/actions/workflows/ci.yml)

</div>

# 蒼狼 AI 可觀測性分析平台 V2.2

歡迎使用「蒼狼 AI 可觀測性分析平台 V2.2」！本專案是一個整合了強大後端 AI 分析能力與現代化前端介面的全端應用程式，旨在提供深入的自動化策略分析報告。

## 目錄
1.  [核心功能](#核心功能)
2.  [快速上手指南：在 Colab 中開啟](#-快速上手指南在-colab-中開啟)
3.  [專案技術架構](#️-專案技術架構)
4.  [開發者指南](#-開發者指南)

## 核心功能

*   **AI 驅動的深度分析報告**：利用先進的 AI模型（如 Google Gemini）自動生成包含量化總結、多元觀點對比及具體行動策略的綜合報告。
*   **結構化報告呈現**：採用 Material Design 的分頁 (Tabs) 介面清晰展示分析結果，取代了以往的原始 JSON 數據，大幅提升資訊的可讀性與使用者體驗。包含以下主要分頁：
    *   **情境分析總結**：展示 AI 對當前情境的量化評估與核心摘要。
    *   **高手觀點碰撞**：以表格形式呈現不同專家或模型的觀點，進行對比分析。
    *   **AI 推薦策略**：詳細列出 AI 建議的操作參數，並結合「看到 -> 想到 -> 做到」的教學框架，提供具體行動指南。
*   **動態金鑰管理**：支援在應用程式運行時透過前端介面安全地設定和更新 API 金鑰。
*   **Google Colab 快速部署**：提供 Colab 筆記本，讓使用者可以一鍵部署並體驗完整功能，優先使用 Colab Secrets 管理 API 金鑰以增強安全性。
*   **(可選) Google Drive 整合**：支援從 Google Drive 自動讀取報告進行分析，適用於進階自動化流程。

## 🚀 快速上手指南：在 Colab 中開啟

本指南為希望快速部署並體驗「蒼狼 AI 可觀測性分析平台」完整功能的使用者設計。透過下方的徽章，您可以一鍵在 Google Colaboratory 中部署並啟動應用程式。

[![在 Colab 中開啟](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/hsp1234-web/wolfAI_v1/blob/main/run_in_colab_v5.ipynb)
*點擊上方徽章，將在新的分頁中開啟 `run_in_colab_v5.ipynb` 筆記本。*

### 第一步：準備您的 API 金鑰 (強烈建議)

為了獲得最完整的分析體驗，建議您先將所需 API 金鑰儲存在 Colab 的「密鑰 (Secrets)」管理器中。這也是 Google 官方推薦的最安全做法。

1.  在打開 Colab 筆記本後，點擊介面左側邊欄的 **鑰匙圖示 (🔑)**，打開「密鑰」分頁。
2.  點擊「新增密鑰」，並依據下表建立您所需要的金鑰。請確保「名稱」欄位與下表完全一致，值則填入您自己的 API Key。

    | 名稱 (Name)             | 用途說明                                     | 狀態 |
    | ----------------------- | -------------------------------------------- |----|
    | `GOOGLE_API_KEY`        | **必需**，用於 Google Gemini AI 核心分析功能。 | 必需 |
    | `API_KEY_FRED`          | (可選) 用於獲取美國聯準會 (FRED) 的經濟數據。   | 可選 |
    | `API_KEY_FINMIND`       | (可選) 用於獲取 FinMind 的台灣金融市場數據。    | 可選 |
    | `API_KEY_FINNHUB`       | (可選) 用於獲取 Finnhub 的國際市場數據。      | 可選 |
    | `API_KEY_FMP`           | (可選) 用於獲取 Financial Modeling Prep 的市場數據。| 可選 |
    | `ALPHA_VANTAGE_API_KEY` | (可選) 用於獲取 Alpha Vantage 的市場數據。    | 可選 |
    | `DEEPSEEK_API_KEY`      | (可選) 用於 DeepSeek 等其他 AI 模型的分析功能。| 可選 |

    > **提示**：如果您暫時沒有某個「可選」金鑰，應用程式**仍然可以啟動**。您稍後可以在部署完成的網頁介面中，進入「系統設定」頁面手動補上或更新。但 `GOOGLE_API_KEY` 對核心 AI 功能至關重要。

### 第二步：執行 Colab 筆記本

在 Colab 筆記本中，通常只有一個程式碼儲存格。請點擊該儲存格左上角的「▶️」(播放) 按鈕來執行。

### 第三步：等待部署完成並訪問應用

點擊播放後，筆記本下方會開始顯示即時的部署日誌。整個過程約需 5-10 分鐘，請耐心等候。成功部署後，日誌區下方通常會出現一個由 `*.googleusercontent.com` (或類似域名) 提供的公開網址，點擊該網址即可開始使用「蒼狼 AI 可觀測性分析平台」。

### 第四步：在網頁中確認或補全金鑰 (若有需要)

如果您在第一步跳過了某些金鑰，或者想確認金鑰狀態，可以在打開的網頁應用程式中找到「系統設定」頁面。該頁面會清楚地顯示各項 API 金鑰的配置狀態，並允許您動態輸入或更新缺失的金鑰。

## 🛠️ 專案技術架構

「蒼狼 AI 可觀測性分析平台」採用現代化的全端架構，各組件分工明確，旨在提供高效能與高擴展性的服務。

### 1. 前端 (Frontend)

*   **框架與語言**：使用 [Next.js](https://nextjs.org/) (基於 [React](https://reactjs.org/)) 和 [TypeScript](https://www.typescriptlang.org/) 進行開發。
*   **UI 元件庫**：採用 [Material-UI (MUI)](https://mui.com/) 打造美觀且符合 Material Design 設計原則 Kullanıcı arayüzü。
*   **核心職責**：
    *   提供使用者互動介面，包括 API 金鑰設定、報告生成觸發等。
    *   以結構化的分頁視圖（情境分析總結、高手觀點碰撞、AI 推薦策略）清晰展示後端生成的分析報告。
    *   與後端 API 進行非同步通訊以獲取和提交資料。

### 2. 後端 (Backend)

*   **框架與語言**：使用 [Python](https://www.python.org/) 及高效能的非同步框架 [FastAPI](https://fastapi.tiangolo.com/) 建構。
*   **核心職責**：
    *   提供 RESTful API 供前端調用。
    *   處理核心的報告生成邏輯，整合 AI 模型進行分析。
    *   管理 API 金鑰的設定與狀態。
    *   與資料庫互動，存取和儲存報告及提示詞等資料。
    *   (可選) 執行排程任務，例如從 Google Drive 定期擷取報告。

### 3. AI 模型整合 (AI Model Integration)

*   **核心模型**：主要利用 [Google Gemini](https://deepmind.google/technologies/gemini/) 系列等先進大型語言模型進行深度分析與策略內容生成。
*   **整合方式**：透過後端服務（`GeminiService`）調用 Google AI 的 API 接口，將分析任務提交給模型處理。

### 4. 資料庫 (Database)

*   **類型**：使用 [SQLite](https://www.sqlite.org/index.html) 作為主要的資料庫系統。
*   **用途**：
    *   `reports.sqlite`：儲存生成的分析報告內容。
    *   `prompts.sqlite`：儲存用於與 AI 模型互動的提示詞模板或歷史記錄。
*   **特性**：輕量級、檔案型資料庫，適合快速部署與開發。在 Colab 環境中，若未掛載 Google Drive，資料庫內容將是暫時性的。

### 5. 金鑰管理與動態配置

*   **Colab 環境**：優先並推薦使用 Colab 的「密鑰 (Secrets)」功能儲存 API 金鑰，透過 `run_in_colab_v5.ipynb` 啟動器讀取。
*   **應用程式內部**：
    *   後端 `config.py` (使用 Pydantic Settings) 管理從環境變數讀取的金鑰。
    *   後端 API (`/api/v1/get_key_status`, `/api/v1/set_keys`) 允許前端查詢及動態更新金鑰。
    *   前端「系統設定」頁面 (`SettingsCard.tsx`) 提供 UI 進行金鑰管理。
*   **設計哲學**：系統設計上強調「優雅降級」，即使部分非核心 API 金鑰缺失，主應用程式仍能啟動並允許使用者後續補齊。

## 👨‍💻 開發者指南

本部分為希望在本地環境進行開發、修改或貢獻專案的開發者提供指引。

### 前置需求

*   [Node.js](https://nodejs.org/) (建議 LTS 版本，用於前端開發)
*   [Python](https://www.python.org/) (建議 3.9+ 版本，用於後端開發)
*   [Git](https://git-scm.com/)

### 專案結構概覽

```
wolfAI_v1/
├── backend/        # 後端 FastAPI 應用程式
│   ├── services/   # 後端服務模組 (例如 GeminiService, DAL)
│   ├── tests/      # 後端測試
│   ├── main.py     # FastAPI 應用主檔案
│   ├── config.py   # Pydantic 設定模型
│   └── requirements.txt
├── data/           # SQLite 資料庫檔案存放位置 (預設)
│   ├── reports.sqlite
│   └── prompts.sqlite
├── frontend/       # 前端 Next.js 應用程式
│   ├── app/        # Next.js App Router 結構
│   ├── components/ # React 元件 (例如 ReportTabs, SettingsCard)
│   ├── public/     # 靜態資源
│   ├── package.json
│   └── tsconfig.json
├── scripts/        # 輔助腳本 (如 start.sh)
├── run_in_colab_v5.ipynb # Colab 部署筆記本
└── README.md
```

### 本地環境設定與啟動

#### 1. 後端 (Backend - FastAPI)

```bash
# 1. 進入後端目錄
cd backend

# 2. (建議) 建立並啟用 Python 虛擬環境
python -m venv venv
# Windows:
# venv\Scripts\activate
# macOS/Linux:
# source venv/bin/activate

# 3. 安裝依賴套件
pip install -r requirements.txt

# 4. 設定必要的環境變數 (可選，但建議用於本地開發)
#    您可以建立一個 .env 檔案在 backend 目錄下，並填入以下內容 (範例):
#    # 此檔案會被 backend/config.py 中的 Pydantic Settings 自動載入
#    GOOGLE_API_KEY="YOUR_GOOGLE_GEMINI_API_KEY"
#    # API_KEY_FRED="YOUR_FRED_KEY"
#    # ... 其他 API 金鑰 ...
#    # WOLF_IN_FOLDER_ID="your_google_drive_folder_id_for_input"
#    # WOLF_PROCESSED_FOLDER_ID="your_google_drive_folder_id_for_processed_files"
#    # OPERATION_MODE="persistent" # 或 "transient"

# 5. 啟動後端開發伺服器 (預設運行於 http://localhost:8000)
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
後端 API 文件 (Swagger UI) 將在 `http://localhost:8000/docs` 可用。

#### 2. 前端 (Frontend - Next.js)

```bash
# 1. 進入前端目錄 (在新的終端機視窗或分頁中)
cd frontend

# 2. 安裝依賴套件
npm install
# 或者如果您使用 yarn:
# yarn install

# 3. 設定前端環境變數 (如果需要)
#    複製 frontend/.env.local.example 為 frontend/.env.local
#    並修改其中的 NEXT_PUBLIC_API_BASE_URL (若後端在本機運行，預設應為 http://localhost:8000)
#    cp .env.local.example .env.local

# 4. 啟動前端開發伺服器 (預設運行於 http://localhost:3000)
npm run dev
# 或者如果您使用 yarn:
# yarn dev
```
開啟瀏覽器並訪問 `http://localhost:3000` 即可看到前端應用程式。

### 執行測試

#### 1. 後端測試 (Pytest)

```bash
# 1. 確保您在後端目錄 (backend/) 且虛擬環境已啟用
cd backend
# source venv/bin/activate (如果尚未啟用)

# 2. 執行測試
pytest
```

#### 2. 前端測試 (Jest & React Testing Library)

```bash
# 1. 確保您在前端目錄 (frontend/)
cd frontend

# 2. 執行測試
npm test
# 或者如果您使用 yarn:
# yarn test
```
