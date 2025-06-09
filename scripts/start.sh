#!/bin/bash
set -e

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
        echo "在 frontend/ 目錄下執行 npm ci --verbose..."
        npm ci --verbose
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
    pushd backend > /dev/null
    if [ "$MODE" == "debug" ]; then
        echo "以除錯模式啟動後端服務 (背景執行，日誌混合輸出至控制台)..."
        nohup python main.py &
        echo "後端服務已在背景啟動 (除錯模式)。"
    else
        echo "以一般模式啟動後端服務 (背景執行，日誌輸出至專案根目錄的 backend.log)..."
        nohup python main.py > ../backend.log 2>&1 &
        echo "後端服務已在背景啟動。日誌請查看 backend.log"
    fi
    popd > /dev/null
}

start_frontend_service() {
    echo "準備啟動前端 Next.js 服務..."
    pushd frontend > /dev/null
    if [ "$MODE" == "debug" ]; then
        echo "以除錯模式啟動前端服務 (背景執行，日誌混合輸出至控制台)..."
        nohup npm run dev -- -p 3000 -H 0.0.0.0 &
        echo "前端服務已在背景啟動 (除錯模式)。"
    else
        echo "以一般模式啟動前端服務 (背景執行，日誌輸出至專案根目錄的 frontend.log)..."
        nohup npm run dev -- -p 3000 -H 0.0.0.0 > ../frontend.log 2>&1 &
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
