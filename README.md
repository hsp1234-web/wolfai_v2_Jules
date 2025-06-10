<div align="center">

[![專案狀態](https://img.shields.io/badge/status-in_development-green.svg)](https://github.com/hsp1234-web/wolfAI_v1)
[![GitHub 最後提交](https://img.shields.io/github/last-commit/hsp1234-web/wolfAI_v1)](https://github.com/hsp1234-web/wolfAI_v1/commits/main)
[![開源授權](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![GitHub 議題](https://img.shields.io/github/issues/hsp1234-web/wolfAI_v1)](https://github.com/hsp1234-web/wolfAI_v1/issues)
[![後端 CI/CD](https://github.com/hsp1234-web/wolfAI_v1/actions/workflows/ci.yml/badge.svg)](https://github.com/hsp1234-web/wolfAI_v1/actions/workflows/ci.yml)

</div>

---

# WolfAI 專案

[![在 Colab 中開啟](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/hsp1234-web/wolfAI_v1/blob/main/run_in_colab_v5.ipynb)

歡迎使用 WolfAI 專案！這是一個整合了強大後端 API 與現代化前端介面的全端應用程式。透過上方的「在 Colab 中開啟」徽章，您可以一鍵部署並體驗完整功能。

本專案採用了最新的金鑰管理方案，優先使用 Colab 內建的「密鑰 (Secrets)」功能，讓您的 API 金鑰更安全、設定更便捷。

-----

## 🚀 快速上手指南

本指南為希望快速部署並體驗應用的使用者設計。

#### **第一步：準備您的 API 金鑰 (強烈建議)**

為了獲得最完整的體驗，建議您先將 API 金鑰儲存在 Colab 的密鑰管理器中。

1.  在打開 Colab 筆記本後，點擊介面左側邊欄的 **鑰匙圖示 (🔑)**，打開「密鑰」分頁。
2.  點擊「新增密鑰」，並依據下表建立您所需要的金鑰。請確保「名稱」欄位與下表完全一致。

| 名稱 (Name)             | 用途說明                                     |
| ----------------------- | -------------------------------------------- |
| `GOOGLE_API_KEY`        | **必需**，用於 Gemini AI 核心分析功能。        |
| `API_KEY_FRED`          | 用於獲取美國聯準會 (FRED) 的經濟數據。         |
| `API_KEY_FINMIND`       | 用於獲取 FinMind 的台灣金融市場數據。          |
| `API_KEY_FINNHUB`       | 用於獲取 Finnhub 的國際市場數據。            |
| `API_KEY_FMP`           | 用於獲取 Financial Modeling Prep 的市場數據。 |
| `ALPHA_VANTAGE_API_KEY` | 用於獲取 Alpha Vantage 的市場數據。          |
| `DEEPSEEK_API_KEY`      | 用於 DeepSeek 等其他 AI 模型的分析功能。     |

> **提示**：如果您暫時沒有某個金鑰也沒關係，應用程式**仍然可以啟動**。您稍後可以在部署完成的網頁介面中，進入「系統設定」頁面手動補上。

#### **第二步：點擊徽章並啟動**

點擊本文件最上方的 [![在 Colab 中開啟](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/hsp1234-web/wolfAI_v1/blob/main/run_in_colab_v5.ipynb) 徽章。在打開的新分頁中，只有一個程式碼儲存格，請點擊該儲存格左上角的「▶️」(播放) 按鈕。

#### **第三步：等待部署並訪問**

點擊播放後，下方會開始顯示即時的部署日誌。整個過程約需 5-10 分鐘，請耐心等候。成功後，日誌區下方會出現一個由 `google.com` 提供的公開網址，點擊即可訪問您的 WolfAI 應用程式。

#### **第四步：在網頁中補全金鑰 (如果需要)**

如果您在第一步跳過了某些金鑰，您可以在打開的網頁應用中，找到「系統設定」頁面。該頁面會清楚地顯示哪些金鑰已設定、哪些缺失，並提供輸入框讓您隨時補全。

-----

## 🛠️ 進階功能與開發者指南

本部分為希望深入了解、修改或貢獻專案的開發者提供詳細的技術解析。

### 系統架構詳解

我們的 v5.0 部署方案圍繞以下核心支柱建構：

1.  **金鑰管理核心：Colab Secrets**
    我們放棄了傳統基於檔案的金鑰管理方式，全面轉向使用 `google.colab.userdata` API。啟動器會自動從 Colab 的密鑰管理器中讀取金鑰，這是 Google 官方推薦的做法，能確保您的金鑰永遠不會暴露在程式碼或輸出日誌中，安全性達到最高。

2.  **優雅降級與動態配置 (Graceful Degradation & Dynamic Configuration)**
    此專案的核心設計理念是「永不因金鑰缺失而啟動失敗」。

      * **後端**：所有依賴外部 API 的服務都被設計為「可選」。如果在啟動時未從環境變數中讀取到對應金鑰，該服務會進入「未配置」狀態，而不是讓整個應用程式崩潰。
      * **前端**：前端的「系統設定」頁面會透過 API (`/api/get_key_status`) 查詢後端的金鑰狀態，並動態渲染出一個管理儀表板，允許使用者在應用程式運行時，透過另一個 API (`/api/set_keys`) 動態注入缺失的金鑰。

3.  **進階功能：Google Drive 整合 (可選)**
    為了支援更進階的、自動化的功能（例如：定時從雲端硬碟讀取特定格式的報告進行分析），我們保留了透過 Google 服務帳號的整合方式。

      * **啟用方式**：這是一項**可選功能**。若要啟用，使用者需將從 Google Cloud Platform 下載的 `service-account.json` 金鑰檔案，放置在自己 Google Drive 的以下路徑：
          * `我的雲端硬碟 / secrets / service-account.json`
      * **運作原理**：當 Colab 啟動器偵測到使用者掛載了雲端硬碟，並且該路徑下存在此檔案時，它會自動設定必要的環境變數，以授權後端服務對您的 Drive 進行讀寫操作。

### 開發者須知

若您想修改或擴充此系統，可以關注以下幾個關鍵檔案：

  * **`run_in_colab_v5.ipynb`**: 整個部署流程的總指揮。它負責讀取 Colab Secrets、設定環境變數、在金鑰缺失時打印警告，並啟動後端與前端。
  * **`backend/config.py`**: Pydantic 設定模型，定義了後端會從環境變數中讀取哪些可選的 API 金鑰。
  * **`backend/main.py`**: FastAPI 應用主體，包含了 `/api/get_key_status` 和 `/api/set_keys` 這兩個用於動態金鑰管理的關鍵端點。
  * **`frontend/components/SettingsCard.tsx`**: (或類似元件) 實現前端金鑰管理儀表板的 React 元件。
