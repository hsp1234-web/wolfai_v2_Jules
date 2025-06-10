#!/bin/bash

# 設定 -e，任何指令失敗時立即退出腳本
set -e

# 為日誌加上時間戳的函數
log_with_timestamp() {
    while IFS= read -r line; do
        echo "[$(date +'%Y-%m-%d %H:%M:%S')] $line"
    done
}

# --- 啟動後端 ---
echo "INFO: 正在設定並啟動後端 FastAPI 伺服器..."
cd backend
echo "INFO: 正在安裝後端依賴..."
pip install -r requirements.txt
echo "INFO: 後端依賴安裝完畢。"
echo "INFO: 正在背景啟動 Uvicorn..."
nohup uvicorn main:app --host 0.0.0.0 --port 8000 2>&1 | log_with_timestamp > ../backend_server.log &
BACKEND_PID=$!
cd ..
echo "SUCCESS: 後端服務已啟動，PID: $BACKEND_PID。"

# --- 啟動前端 ---
echo "INFO: 正在設定並啟動前端 Next.js 伺服器..."
cd frontend
echo "INFO: 正在安裝前端依賴 (npm install)..."
npm install
echo "INFO: 前端依賴安裝完畢。"
echo "INFO: 正在背景啟動 Next.js 開發伺服器..."
nohup npm run dev 2>&1 | log_with_timestamp > ../frontend_server.log &
FRONTEND_PID=$!
cd ..
echo "SUCCESS: 前端服務已啟動，PID: $FRONTEND_PID。"

echo "----------------------------------------------------"
echo "所有服務已啟動。請檢查日誌檔案以確認狀態："
echo "  - 後端日誌: backend_server.log"
echo "  - 前端日誌: frontend_server.log"
echo "----------------------------------------------------"
