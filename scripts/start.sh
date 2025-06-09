#!/bin/bash
# 腳本開頭依然使用 set -e，確保任何命令失敗都會立即停止腳本，防止後續問題。
set -e

# --- 參數處理 ---
MODE="normal" # 預設啟動模式為 "normal"
for arg in "$@"; do
    case $arg in
        --mode=*)
        MODE="${arg#*=}"
        shift
        ;;
    esac
done
echo "[start.sh] INFO: 偵測到的啟動模式: $MODE"

# --- 依賴安裝 (增加錯誤處理和詳細日誌) ---
echo "[start.sh] INFO: 開始安裝後端 Python 依賴..."
# 增加 --verbose 選項並捕獲錯誤
if ! pip install -r backend/requirements.txt --no-cache-dir --verbose; then
    echo "[start.sh] FATAL: 後端 Python 依賴安裝失敗。請檢查上面的日誌輸出。"
    exit 1
fi
echo "[start.sh] SUCCESS: 後端 Python 依賴已成功安裝。"

echo "[start.sh] INFO: 開始安裝前端 Node.js 依賴..."
# 對 npm install 也增加詳細日誌和錯誤捕獲
# 使用 (cd ... && ...) 確保命令在正確的目錄下執行
if ! (cd frontend && npm install --verbose); then
    echo "[start.sh] FATAL: 前端 Node.js 依賴安裝失敗。請檢查上面的日誌輸出。"
    exit 1
fi
echo "[start.sh] SUCCESS: 前端 Node.js 依賴已成功安裝。"


# --- 服務啟動 ---
# 根據模式決定啟動方式
if [ "$MODE" == "debug" ]; then
    echo "[start.sh] INFO: 以除錯模式啟動服務 (日誌將直接輸出至此控制台)..."
    (cd backend && python main.py) &
    BACKEND_PID=$!
    echo "[start.sh] INFO: 後端服務已啟動，PID: $BACKEND_PID"

    (cd frontend && npm run dev -- -p 3000 -H 0.0.0.0) &
    FRONTEND_PID=$!
    echo "[start.sh] INFO: 前端服務已啟動，PID: $FRONTEND_PID"

    echo "[start.sh] INFO: 除錯模式：等待後端 (PID: $BACKEND_PID) 和前端 (PID: $FRONTEND_PID) 進程結束..."
    wait $BACKEND_PID $FRONTEND_PID
    echo "[start.sh] INFO: 後端和前端服務均已結束 (除錯模式)。"
else
    echo "[start.sh] INFO: 以一般模式在背景啟動服務 (日誌將輸出至檔案)..."
    LOG_DIR="/content/logs" # 修改日誌目錄
    mkdir -p "$LOG_DIR" # 創建日誌目錄
    echo "[start.sh] INFO: 啟動後端服務 (Python FastAPI) 並將日誌導向 ${LOG_DIR}/backend.log..."
    nohup python backend/main.py > "${LOG_DIR}/backend.log" 2>&1 &

    echo "[start.sh] INFO: 啟動前端服務 (Node.js Next.js) 並將日誌導向 ${LOG_DIR}/frontend.log..."
    nohup npm run dev --prefix frontend -- -p 3000 -H 0.0.0.0 > "${LOG_DIR}/frontend.log" 2>&1 &

    echo "[start.sh] SUCCESS: 服務已在背景啟動。日誌檔案位於 ${LOG_DIR} 目錄下。"
fi

echo "[start.sh] INFO: 腳本執行流程結束。"
