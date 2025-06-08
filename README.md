# Wolf AI 可觀測性分析平台 - V2.2

[![在 Colab 中開啟](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/hsp1234-web/wolfAI_v1/blob/main/run_in_colab.ipynb)

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
*   **雙操作模式**: 支援「暫存模式」（快速啟動，資料不落地）與「持久模式」（整合 Google Drive，資料永久保存）。

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

蒼狼 AI V1 採用了全新的「一鍵部署」流程，大幅簡化了在 Google Colaboratory 中的啟動過程。

1.  **點擊 "Open in Colab" 徽章**:
    *   點擊本文件最上方的 [![在 Colab 中開啟](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/hsp1234-web/wolfAI_v1/blob/main/run_in_colab.ipynb) 徽章，即可在 Colab 中打開 `run_in_colab.ipynb` 筆記本。

2.  **執行唯一的程式碼儲存格**:
    *   筆記本現在只包含一個主要的程式碼儲存格。依照儲存格內的中文提示，逐步執行即可完成所有設定與啟動。

3.  **選擇操作模式**:
    *   在執行儲存格的初期，您將看到一個「選擇操作模式」的下拉選單。您可以選擇：
        *   **暫存模式 (transient)**：此模式為預設選項，無需 Google Drive 授權即可快速啟動應用程式。所有資料（如上傳的報告、資料庫）將僅儲存在當前的 Colab 會話中，會話結束後資料將會遺失。此模式適用於快速體驗或不需要資料保存的場景。
        *   **持久模式 (persistent)**：此模式需要您授權 Colab 掛載您的 Google Drive，並設定相關的雲端儲存密鑰。所有資料將會儲存到您指定的 Google Drive 路徑，從而實現資料的永久保存和跨會話使用。
    *   請根據您的需求選擇合適的模式。如果選擇「持久模式」，請確保已正確設定後述的 Colab Secrets。

### 主要自動化步驟概覽

該程式碼儲存格將自動執行以下核心步驟：

*   **操作模式選擇**: 如上所述，允許使用者選擇「暫存模式」或「持久模式」。後續步驟的行為（如 Drive 掛載、Secrets 檢查）將依此選擇而定。
*   **Google Drive 掛載**: 如果選擇「持久模式」，則提示並協助您授權 Colab 存取您的 Google Drive。暫存模式下跳過此步驟。
*   **Colab Secrets 設定引導與檢查**:
    *   引導您在 Colab 的「密鑰 (Secrets)」管理器中設定必要的金鑰。
    *   `COLAB_GOOGLE_API_KEY` (用於 Google AI 服務)：建議在兩種模式下都設定。
    *   `GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT` (用於 Google Drive 存取), `WOLF_IN_FOLDER_ID` (Drive 中存放待處理報告的資料夾 ID), `WOLF_PROCESSED_FOLDER_ID` (Drive 中存放已處理報告的資料夾 ID)：這些主要在「持久模式」下是必需的。
    *   在執行後續步驟前，腳本會根據所選操作模式檢查相應的 Secrets 是否均已設定，若有缺失則會提示並終止執行。
*   **應用程式啟動模式選擇**: 您可以在儲存格內選擇應用程式後端和前端服務的啟動模式（`normal` 或 `debug`）。此選擇與操作模式（暫存/持久）是獨立的。
*   **專案部署與服務啟動**:
    *   自動從 GitHub (`https://github.com/hsp1234-web/wolfAI_v1.git`) 複製最新的專案程式碼。
    *   執行位於專案中 `scripts/start.sh` 的主控啟動腳本。此腳本會：
        *   根據所選模式，安裝後端 Python 依賴和前端 Node.js 依賴。
        *   根據所選模式，啟動後端 FastAPI 服務和前端 Next.js 服務。在 `normal` 模式下，服務會在背景執行，並將日誌輸出到專案根目錄下的 `backend.log` 和 `frontend.log`；在 `debug` 模式下，服務日誌會直接輸出到 Colab 儲存格。
*   **健康檢查與顯示結果**:
    *   在啟動服務後，腳本會執行健康檢查，確認後端和前端服務是否都已成功啟動並正常回應。
    *   成功後，會嘗試顯示由 Colab 提供的公開訪問網址，您可以點擊該網址開始使用蒼狼 AI 平台。

### Colab Secrets 的重要性

為了確保應用程式能夠順利運行並存取必要的雲端服務，請務必依照 Colab 筆記本內的引導，在「密鑰 (Secrets)」管理器中正確設定以下項目：

*   **`COLAB_GOOGLE_API_KEY`**: 您的 Google AI 服務 API 金鑰。
    *   **重要性**: 在「暫存模式」和「持久模式」下都**強烈建議設定**，以確保 AI 分析功能可用。如果未設定，AI 對話和分析將無法進行。
*   **`GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT`**: 您的 Google Cloud 服務帳號金鑰的 JSON **內容** (需具備 Drive 存取權限)。
    *   **重要性**: 主要在「**持久模式**」下**必需**。用於授權應用程式存取您的 Google Drive 以讀取報告、儲存資料庫等。
    *   在「暫存模式」下，此密鑰不是必需的，因為應用程式不會嘗試連接到 Google Drive。
*   **`WOLF_IN_FOLDER_ID`**: Google Drive 中用於存放**待處理報告**的資料夾 ID。
    *   **重要性**: 主要在「**持久模式**」下**必需**。指定應用程式從哪個 Drive 資料夾讀取新的報告檔案。
    *   在「暫存模式」下不是必需的。
*   **`WOLF_PROCESSED_FOLDER_ID`**: Google Drive 中用於存放**已處理報告**的資料夾 ID。
    *   **重要性**: 主要在「**持久模式**」下**必需**。指定已處理報告在 Drive 中的歸檔位置。
    *   在「暫存模式」下不是必需的。

**設定建議**：
*   **持久模式**: 請務必完整設定上述所有四個密鑰。建議您在首次執行筆記本前，預先在自己的 Google Drive 中創建 `wolf_AI_data` 資料夾，並在其下創建 `wolf_in` 和 `wolf_in/processed` 子資料夾。然後將這些資料夾的 ID 填入 Colab Secrets。如果您的 Drive 中已有 `reports.sqlite` 和 `prompts.sqlite` 資料庫檔案，請將它們放置於 `wolf_AI_data` 目錄下，後端服務啟動時會嘗試使用它們。
*   **暫存模式**: `COLAB_GOOGLE_API_KEY` 仍然是推薦設定的，以使用 AI 功能。其他三個 Drive 相關密鑰可以不設定。應用程式在此模式下會使用 Colab 本地的臨時儲存空間。

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
