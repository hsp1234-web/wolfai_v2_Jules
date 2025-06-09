#!/bin/bash

# --- 參數處理 ---
MODE="normal" # 預設模式

# 解析命令行參數
for arg in "$@"
do
    case $arg in
        --mode=*)
        MODE="${arg#*=}"
        shift # 移除 --mode=debug
        ;;
    esac
done

echo "啟動模式: $MODE"

# --- 環境偵測 ---
IN_COLAB=false
if [ -n "$COLAB_GPU" ] || [ -n "$DATALAB_SETTINGS_OVERRIDES" ]; then
    IN_COLAB=true
fi
echo "是否在 Colab 環境中: $IN_COLAB"

# --- 依賴安裝 ---
install_backend_dependencies() {
    echo "正在檢查並安裝後端 Python 依賴 (from backend/requirements.txt)..."
    if [ -f "backend/requirements.txt" ]; then
        pip install -r backend/requirements.txt -q --no-warn-script-location
        echo "後端 Python 依賴已成功安裝。"
    else
        echo "錯誤：後端依賴定義檔 backend/requirements.txt 未找到。"
        exit 1 # set -e 會處理退出，但明確指出錯誤更好
    fi
}

install_frontend_dependencies() {
    echo "正在檢查並安裝前端 Node.js 依賴 (from frontend/package.json)..."
    if [ -f "frontend/package.json" ]; then
        echo "切換到 frontend/ 目錄..."
        pushd frontend > /dev/null # > /dev/null 避免 pushd 的額外輸出
        echo "在 frontend/ 目錄下執行 npm ci..." # Removed --verbose from original plan
        npm ci
        echo "前端 Node.js 依賴已成功安裝。"
        popd > /dev/null # 返回先前目錄
    else
        echo "錯誤：前端依賴定義檔 frontend/package.json 未找到。"
        exit 1 # set -e 會處理退出
    fi
}

# --- 服務啟動 ---
start_backend_service() {
    echo "準備啟動後端 FastAPI 服務..."
    # 不再需要進入 backend 目錄
    if [ "$MODE" == "debug" ]; then
        echo "以除錯模式啟動後端服務 (從專案根目錄執行，背景執行，日誌混合輸出至控制台)..."
        # 使用 -m 選項從專案根目錄執行
        nohup python -m backend.main & # nohup.out will be in /app
        echo "後端服務已在背景啟動 (除錯模式)。"
    else
        echo "以一般模式啟動後端服務 (從專案根目錄執行，背景執行，日誌輸出至專案根目錄的 backend.log)..."
        # 使用 -m 選項從專案根目錄執行
        nohup python -m backend.main > backend.log 2>&1 &
        echo "後端服務已在背景啟動。日誌請查看 backend.log"
    fi
}

start_frontend_service() {
    echo "準備啟動前端 Next.js 服務..."
    FRONTEND_PORT=3000
    echo "嘗試強制終止任何已在運行的舊前端進程 (端口 ${FRONTEND_PORT})..."
    pkill -9 -f "npm run dev.*-- -p ${FRONTEND_PORT}" || true
    pkill -9 -f "next dev.*-p ${FRONTEND_PORT}" || true
    sleep 1 # 短暫等待進程終止
    echo "檢查端口 ${FRONTEND_PORT} 是否被占用..."
    PID=$(lsof -t -i:${FRONTEND_PORT} 2>/dev/null)

    if [ -n "$PID" ]; then
        echo "警告：端口 ${FRONTEND_PORT} 已被進程 ID ${PID} 占用。正在嘗試終止舊進程..."
        kill -9 "$PID"
        sleep 2 # 等待進程終止
        echo "舊進程 ID ${PID} 已被終止。"
    else
        echo "端口 ${FRONTEND_PORT} 可用。"
    fi

    pushd frontend > /dev/null
    if [ "$MODE" == "debug" ]; then
        echo "以除錯模式啟動前端服務 (背景執行，日誌混合輸出至控制台)..."
        nohup npm run dev -- -p ${FRONTEND_PORT} -H 0.0.0.0 & # nohup.out will be in /app/frontend
        echo "前端服務已在背景啟動 (除錯模式)。"
    else
        echo "以一般模式啟動前端服務 (背景執行，日誌輸出至專案根目錄的 frontend.log)..."
        nohup npm run dev -- -p ${FRONTEND_PORT} -H 0.0.0.0 > ../frontend.log 2>&1 &
        echo "前端服務已在背景啟動。日誌請查看 frontend.log"
    fi
    popd > /dev/null
}

# --- 主執行流程 ---
echo "--- 開始執行啟動腳本 ---"

install_backend_dependencies
install_frontend_dependencies
start_backend_service
start_frontend_service

echo "--- 啟動腳本執行完畢 ---"
