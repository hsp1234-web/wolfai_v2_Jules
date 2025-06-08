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

1.  **點擊上方的 "Open in Colab" 徽章**。
2.  在打開的 Colab 筆記本 (`run_in_colab.ipynb`) 中，**按照儲存格的說明逐步執行**：
    *   **第一步：環境設定與授權**: 掛載您的 Google Drive，並根據提示設定 Google API 金鑰（服務帳號金鑰或 Colab Secret）。
    *   **第二步：複製專案程式碼與安裝依賴**: 筆記本會自動從 GitHub 複製最新程式碼並安裝所有後端和前端依賴。
    *   **第三步：準備 Google Drive 資料夾與資料庫檔案**: 筆記本會輔助您在 Drive 中創建必要的資料夾結構，並引導您設定相關的 Colab Secrets (如 `WOLF_IN_FOLDER_ID`)。它也會嘗試從 Drive 下載現有的資料庫檔案到 Colab 環境。
    *   **第四步：啟動應用程式服務與健康度偵測**: 此儲存格會啟動後端 API 伺服器和前端 Next.js 網站。執行後，請留意 Colab 的輸出，它通常會提供一個公開的網址 (類似 `https://....colab.research.google.com/` 或 `https://....googleusercontent.com/`)，您可以透過該網址訪問應用程式。
3.  **開始使用**: 服務成功啟動後，點擊 Colab 提供的公開網址即可開始使用 Wolf AI V2.2 平台。

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
