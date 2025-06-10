# Wolf AI 可觀測性分析平台 - V2.2

[![在 Colab 中開啟](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/hsp1234-web/wolfAI_v1/blob/main/run_in_colab.ipynb)

## 專案摘要

Wolf AI V2.2 是一個旨在幫助使用者深入分析、總結並問答各類報告內容（初期以週報為主）的 AI 對話系統。此版本從靜態檔案系統架構全面升級，以 Google Drive 為後盾、雙 SQLite 資料庫為核心，實現動態資料管理。前端採用 Google Material Design 3 (M3) 設計語言，透過卡片式的引導流程優化使用者體驗。後端遵循全面異步、高內聚、低耦合的模組化原則設計，並具備完善的單元測試和程式碼風格檢查。專案以 Google Colab 為核心部署環境，整合其原生功能，提供引導式、全繁體中文化的啟動體驗和主動式健康回報機制，確保系統的穩定性與易用性。

## 主要功能

* **上下文理解的 AI 對話**: 利用 AI 模型進行多輪對話，深入分析報告內容。
* **動態報告匯入**: 支援從 Google Drive 指定資料夾（持久模式下）自動擷取新報告，或透過網頁介面直接上傳檔案。
* **引導式使用者體驗**: 現代化的卡片式操作流程（設定 API 金鑰 -> 選擇/上傳檔案 -> 互動對話 -> 檢視分析結果），所有主要介面均提供清晰的繁體中文指引。
* **Google Drive 整合 (持久模式)**:
    * 核心資料庫 (`reports.sqlite`, `prompts.sqlite`) 可選擇存儲於使用者的 Google Drive 中，確保資料的持久性。
    * 報告檔案在 Drive 中的指定資料夾 (`wolf_in` 用於待處理報告，`wolf_in/processed` 用於已處理報告的歸檔) 進行管理。
* **彈性的金鑰管理**: 優先從 Colab 環境密鑰讀取 Google API 金鑰，若未配置，則引導使用者在前端介面輸入並即時設定。支援 API 金鑰設定狀態的查詢。
* **Colab 一鍵部署與操作**: 透過 `run_in_colab.ipynb` 筆記本提供步驟化、全繁體中文化的引導，簡化環境設定、依賴安裝及服務啟動流程。
* **雙操作模式**:
    * **暫存模式 (Transient Mode)**：快速啟動，無需 Google Drive 授權，資料僅在當前 Colab 會話中保留，適合快速演示與測試。
    * **持久模式 (Persistent Mode)**：整合 Google Drive，所有報告資料、資料庫及設定將永久保存在使用者的雲端硬碟中。
* **主動式健康回報**:
    * 提供 `/api/health` 和 `/api/health/verbose` API 端點，以繁體中文回報後端各關鍵服務（資料庫、AI服務、Drive服務、排程器等）的運行狀態。
    * Colab 筆記本整合了健康檢查步驟，方便使用者確認系統是否正常運作。
* **專業化工程實踐**:
    * **API 契約優先**: 後端 API 提供詳細的 OpenAPI 3.1 規格文件 (`openapi.json`)，所有描述均已中文化，方便前端整合與第三方調用。
    * **程式碼品質保證**: 整合 `flake8` (後端 Python) 和 `eslint` (前端 TypeScript/TSX) 進行靜態程式碼分析與風格檢查。
    * **自動化測試**: 包含後端服務的單元測試 (`pytest`) 和前端組件的基礎測試 (`Jest`)，並提供 `scripts/run_tests.sh` 腳本執行完整的檢查與測試流程。
    * **清晰的專案結構**: 模組化的服務設計，易於理解和擴展。

## 技術棧

### 後端
* **框架**: FastAPI
* **語言**: Python 3.10+
* **資料庫**: SQLite (透過 `aiosqlite` 進行異步操作)
* **雲端儲存**: Google Drive API (透過 `aiogoogle` 和 `google-api-python-client`)
* **背景任務**: APScheduler
* **程式碼風格與品質**: Flake8
* **主要依賴**: `fastapi`, `uvicorn`, `aiosqlite`, `APScheduler`, `google-api-python-client`, `aiogoogle`, `pydantic`, `python-dotenv`

### 前端
* **框架**: Next.js (React)
* **語言**: TypeScript
* **UI 元件庫**: MUI (Material-UI) - 實現 Google Material Design 3 風格
* **程式碼風格與品質**: ESLint
* **主要依賴**: `next`, `react`, `react-dom`, `@mui/material`, `@emotion/react`, `@emotion/styled`

### 測試
* **後端**: Pytest (單元測試、整合測試)
* **前端**: Jest, React Testing Library (單元測試、組件測試)
* **自動化測試腳本**: Bash scripts (`scripts/run_tests.sh`) 整合風格檢查與單元測試。

### API 文件
* **標準**: OpenAPI (透過 FastAPI 自動生成)
* **生成腳本**: `scripts/export_api_schema.py`

### 部署
* **核心環境**: Google Colaboratory (`run_in_colab.ipynb` 筆記本)
* **版本控制**: Git & GitHub

## 如何啟動

### 使用 "Open in Colab" 徽章 (建議方法)

蒼狼 AI V2.2 提供了強化的 Colab 筆記本 (`run_in_colab.ipynb`)，實現了引導式、步驟化的部署體驗。

1.  **點擊 "Open in Colab" 徽章**:
    *   點擊本文件最上方的 [![在 Colab 中開啟](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/hsp1234-web/wolfAI_v1/blob/main/run_in_colab.ipynb) 徽章，即可在 Google Colaboratory 中打開最新的部署筆記本。

2.  **依照筆記本中的步驟執行**:
    *   **步驟 1: 環境設定與授權**:
        *   此儲存格允許您選擇「操作模式」（暫存或持久）、「GitHub 分支」以及「啟動模式」（一般或除錯）。
        *   所有選項和說明均已中文化。
        *   **暫存模式 (transient)**：無需 Google Drive 授權即可快速啟動。所有資料（包括資料庫）僅儲存在當前 Colab 會話中，會話結束後資料將遺失。此模式適用於快速體驗或不需要資料保存的場景。AI 分析功能可能因未設定 API 金鑰而受限。
        *   **持久模式 (persistent)**：需要您授權 Colab 掛載您的 Google Drive。應用程式資料（包括資料庫）將儲存於您 Google Drive 中的 `wolfAI_Data` 資料夾，實現資料的永久保存和跨會話使用。此模式下，您需要在 Colab 的「密鑰 (Secrets)」管理器中設定必要的雲端服務金鑰 (詳見筆記本內的說明)。
        *   選擇完成後，點擊「確認設定並掛載雲端硬碟 (若選擇)」按鈕。
    *   **步驟 2: 安裝依賴與啟動服務**:
        *   此儲存格將自動從指定的 GitHub 分支下載最新程式碼。
        *   接著，它會執行專案內的 `scripts/start.sh` 腳本，該腳本負責安裝所有後端 Python 依賴和前端 Node.js 依賴，然後啟動後端 FastAPI 服務和前端 Next.js 服務。
        *   啟動過程的日誌會顯示在儲存格輸出中。若發生端口衝突（例如端口 3000 已被佔用），腳本會提示相關錯誤。
    *   **步驟 3: 健康檢查與獲取訪問連結**:
        *   服務啟動後，此儲存格會執行健康檢查，輪詢後端 `/api/health` 端點，直到服務就緒或超時。
        *   健康檢查的狀態和後端各組件的狀態（例如資料庫、AI服務、Drive服務）會以繁體中文展示。
        *   一旦後端和前端服務均成功啟動，將會生成並顯示一個可點擊的前端訪問連結（通常是 `googleusercontent.com` 的網域）。

3.  **設定 Colab Secrets (金鑰管理)**:
    *   為了應用程式功能的完整性（特別是 AI 分析和持久模式下的 Google Drive 操作），您需要在 Colab 環境的「密鑰 (Secrets)」管理器中設定以下金鑰。筆記本的步驟 1 輸出區域會引導您進行設定：
        *   `COLAB_GOOGLE_API_KEY`: 您的 Google AI 服務 API 金鑰 (例如 Gemini API)。AI 分析功能依賴此金鑰。
        *   `GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT`: (持久模式必需) 您的 Google Cloud 服務帳號金鑰的完整 JSON **內容**。請確保此服務帳號擁有對您 Google Drive 的讀寫權限。
        *   `WOLF_IN_FOLDER_ID`: (持久模式必需) 您在 Google Drive 中指定的「待處理報告」來源資料夾的 ID。
        *   `WOLF_PROCESSED_FOLDER_ID`: (持久模式必需) 您在 Google Drive 中指定的「已處理報告」歸檔資料夾的 ID。
    *   **建議**：即使是「暫存模式」，也建議設定 `COLAB_GOOGLE_API_KEY` 以體驗完整的 AI 功能。對於「持久模式」，上述所有四個金鑰都是必要的。

### 方法二：本機開發與部署 (進階)

（此部分可根據實際的本機部署指南進行擴充，目前 Colab 是主要部署方式。）

對於希望在本機環境進行開發或部署的使用者：

1.  **環境要求**:
    *   Python 3.10 或更高版本。
    *   Node.js (建議 LTS 版本)。
    *   Poetry (用於 Python 依賴管理，可選但建議)。
    *   Git。
2.  **後端設定**:
    *   克隆本專案。
    *   進入 `backend/` 目錄。
    *   設定必要的環境變數 (參考 `.env.example` 或 Colab Secrets 中的金鑰名稱)。可以創建一個 `.env` 檔案來管理這些變數。
    *   安裝依賴：`pip install -r requirements.txt` (或使用 Poetry: `poetry install`)。
    *   啟動後端：`python main.py` 或 `uvicorn main:app --reload`。
3.  **前端設定**:
    *   進入 `frontend/` 目錄。
    *   安裝依賴：`npm install`。
    *   啟動前端開發伺服器：`npm run dev`。

詳細的本機部署步驟和配置請參考專案內更詳細的開發文檔（如果提供）。

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
├── openapi.json        # 自動生成的 API契約檔案
```

## 測試與品質保證

本專案致力於確保程式碼品質和功能的穩定性，整合了以下測試與檢查流程：

*   **後端測試 (`pytest`)**:
    *   針對 API 端點 (`backend/tests/api/`) 和核心服務 (`backend/tests/services/`) 編寫了單元測試和部分整合測試。
    *   測試案例涵蓋了成功路徑、錯誤處理和邊界條件。
    *   所有外部依賴（如資料庫、Google Drive API、Gemini API）均使用 `pytest-mock` 和 `unittest.mock` 進行模擬，確保測試的獨立性和可重複性。
*   **前端測試 (`Jest` 與 `React Testing Library`)**:
    *   （基礎結構已建立，但詳細測試案例待根據前端複雜度增加而補充）
    *   目標是覆蓋關鍵 UI 組件的渲染和基本交互。
*   **程式碼風格與品質檢查**:
    *   **後端**: 使用 `flake8` 進行 Python 程式碼風格檢查，確保代碼一致性和可讀性。
    *   **前端**: 使用 `ESLint` (整合 `eslint-config-next`) 進行 TypeScript/TSX 程式碼的風格和潛在錯誤檢查。
*   **自動化 API Schema 導出**:
    *   提供 `scripts/export_api_schema.py` 腳本，用於從運行的後端服務自動生成 `openapi.json` 檔案，確保 API 文件與實現同步。
*   **整合測試腳本 (`scripts/run_tests.sh`)**:
    *   此腳本自動執行後端 `flake8` 檢查、後端 `pytest` 單元測試、API schema 導出、前端 `ESLint` 檢查以及前端 `Jest` 測試。
    *   任何步驟失敗都會導致腳本以錯誤狀態退出，適用於本地開發和持續整合 (CI) 環境。

所有測試和檢查的目標是提升開發效率、降低錯誤引入的風險，並確保專案的長期可維護性。

## 貢獻

(如果接受貢獻，請在此處添加指南)

## 授權條款

(請在此處註明您的專案授權，例如 MIT, Apache 2.0 等)
