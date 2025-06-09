#!/bin/bash
# set -e # 根據要求移除

# --- 參數處理 ---
MODE="normal" # 預設模式

# 解析命令行參數
for arg in "$@"
do
    case $arg in
        --mode=*)
        MODE="${arg#*=}"
        shift # 移除 --mode=xxx 參數本身
        ;;
    esac
done

echo "啟動模式: $MODE"

# --- 環境偵測 ---
IN_COLAB=false
if [ -n "$COLAB_GPU" ] || [ -n "$DATALAB_SETTINGS_OVERRIDES" ]; then
    IN_COLAB=true
fi
echo "是否在 Colab 環境中: $IN_COLAB" # 這條訊息主要是開發者參考，可保留英文或簡單翻譯

# --- 通用指令執行函數 ---
# 此函數接受兩個參數:
# $1: 指令描述 (用於日誌輸出)
# $2: 要執行的實際指令
run_command() {
    local description="$1"
    local command_to_run="$2"

    echo "正在執行: $description..."
    # 執行指令，並捕獲其輸出和錯誤
    # 在這裡，我們讓指令的輸出直接打印到控制台，因為某些指令（如 npm ci）的詳細輸出可能有用
    if eval "$command_to_run"; then
        echo "成功: $description 完成。"
    else
        local exit_code=$?
        echo "錯誤: $description 失敗，結束狀態碼 $exit_code。"
        exit $exit_code # 腳本以相同的錯誤碼退出
    fi
}

# --- 依賴安裝 ---
install_backend_dependencies() {
    echo "檢查並安裝後端 Python 依賴 (來源: backend/requirements.txt)..."
    if [ -f "backend/requirements.txt" ]; then
        # 使用 run_command 執行 pip install
        run_command "安裝後端 Python 依賴" "pip install -r backend/requirements.txt -q --no-warn-script-location"
    else
        echo "錯誤：後端依賴定義檔 backend/requirements.txt 未找到。"
        exit 1
    fi
}

install_frontend_dependencies() {
    echo "檢查並安裝前端 Node.js 依賴 (來源: frontend/package.json)..."
    if [ -f "frontend/package.json" ]; then
        echo "切換到 frontend/ 目錄..."
        pushd frontend > /dev/null # > /dev/null 避免 pushd 的額外輸出
        # 使用 run_command 執行 npm ci
        run_command "安裝前端 Node.js 依賴" "npm ci --verbose"
        popd > /dev/null # 返回先前目錄
    else
        echo "錯誤：前端依賴定義檔 frontend/package.json 未找到。"
        exit 1
    fi
}

# --- 服務啟動 ---
start_backend_service() {
    echo "準備啟動後端 FastAPI 服務..."
    pushd backend > /dev/null
    if [ "$MODE" == "debug" ]; then
        echo "以除錯模式啟動後端服務 (日誌將直接輸出至此)..."
        # 直接執行，不使用 nohup，日誌會直接輸出到 Colab cell (或終端)
        python main.py &
        echo "後端服務已在背景啟動 (除錯模式)。"
    else
        echo "以一般模式啟動後端服務 (日誌輸出至專案根目錄的 backend.log)..."
        nohup python main.py > ../backend.log 2>&1 &
        echo "後端服務已在背景啟動。日誌請查看 backend.log"
    fi
    popd > /dev/null
}

start_frontend_service() {
    echo "準備啟動前端 Next.js 服務..."
    pushd frontend > /dev/null
    if [ "$MODE" == "debug" ]; then
        echo "以除錯模式啟動前端服務 (日誌將直接輸出至此)..."
        # 直接執行，不使用 nohup
        npm run dev -- -p 3000 -H 0.0.0.0 &
        echo "前端服務已在背景啟動 (除錯模式)。"
    else
        echo "以一般模式啟動前端服務 (日誌輸出至專案根目錄的 frontend.log)..."
        nohup npm run dev -- -p 3000 -H 0.0.0.0 > ../frontend.log 2>&1 &
        echo "前端服務已在背景啟動。日誌請查看 frontend.log"
    fi
    popd > /dev/null
}

# --- 主執行流程 ---
echo "--- 開始執行啟動腳本 (蒼狼 AI V2.2) ---"

install_backend_dependencies
install_frontend_dependencies
start_backend_service
start_frontend_service

echo "--- 啟動腳本執行完畢 ---"
echo "提示：服務啟動可能需要一些時間。請檢查 Colab 的輸出或日誌檔案以確認狀態。"
echo "如果服務正常，前端應用程式將可透過 Colab 指派的 URL 訪問 (通常監聽端口 3000)。"
echo "後端 API 服務通常監聽端口 8000。"
