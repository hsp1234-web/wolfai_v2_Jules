# 🚀 蒼狼 AI 可觀測性分析平台 - V2.2

[![在 Colab 中開啟](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/hsp1234-web/wolfAI_v1/blob/main/run_in_colab.ipynb)

## 這是什麼？

蒼狼 AI 是一個聰明的對話助理，能幫您深入分析、總結各種報告（像是週報、會議記錄等），並回答您關於報告內容的任何問題。

想像一下，您再也不用花大把時間消化長篇大論的文件，只需和 AI 聊聊天，就能快速掌握重點！

## 主要亮點

* **智慧對話**：像跟真人聊天一樣，與 AI 深入探討報告細節。
* **自動匯入**：把報告檔案丟進 Google Drive 的指定資料夾，系統就會自動讀取。
* **簡單易用**：全新的卡片式介面，引導您一步步完成「設定 → 選檔案 → 開始分析」的流暢操作。
* **資料安全**：您可以選擇將所有資料保存在自己的 Google Drive 中，安全又放心。
* **一鍵啟動**：無需複雜設定，只需點擊上方的 "Open in Colab" 徽章，即可在雲端啟動您的專屬分析平台。

## 如何開始？(超級簡單！)

我們推薦使用「一鍵部署」流程，這是有史以來最簡單的方式：

1.  **點擊上方徽章**：點擊本文件最上方的 [![在 Colab 中開啟](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/hsp1234-web/wolfAI_v1/blob/main/run_in_colab.ipynb) 徽章。

2.  **在新開的 Colab 頁面中做選擇**：
    您會看到一個設定區塊，只需決定一件事：
    * **嚐鮮一下 (暫存模式)**：最快啟動！適合快速體驗。所有資料在您關閉分頁後會消失。
    * **正式使用 (持久模式)**：需要您授權 Google Drive。您的報告和設定都會安全地保存在您的雲端硬碟。

3.  **點擊「播放」按鈕**：
    完成選擇後，點擊設定區塊左側的 ▶️ (播放) 按鈕。

4.  **稍等片刻，大功告成**！
    程式碼會自動跑完，過程大約需要 2-3 分鐘。完成後，您會看到一個公開網址，點下去就可以開始使用蒼狼 AI 平台了！

## 給技術夥伴的參考 (Technical Stack)

* **後端**: Python, FastAPI, aiosqlite, Google Drive API
* **前端**: TypeScript, Next.js, React, Material-UI (MUI)
* **部署**: Google Colaboratory

---
