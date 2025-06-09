#!/bin/bash
set -e # 啟用錯誤立即退出

# --- 參數處理 ---
MODE="normal" # 預設啟動模式為 "normal"

# 解析命令行參數以取得模式設定
# 例如，允許執行 ./start.sh --mode=debug
for arg in "$@"
do
    case $arg in
        --mode=*)
        MODE="${arg#*=}" # 提取等號後的模式值
        shift # 移除已處理的參數
        ;;
    esac
done

echo "[start.sh] 偵測到的啟動模式: $MODE"

# --- 環境偵測 (可選，主要為 Colab 環境提供參考) ---
IN_COLAB=false
if [ -n "$COLAB_GPU" ] || [ -n "$DATALAB_SETTINGS_OVERRIDES" ]; then
    IN_COLAB=true
fi
echo "[start.sh] 是否在 Colab 環境中: $IN_COLAB"

# --- 依賴安裝 ---
echo "[start.sh] 正在安裝後端 Python 依賴 (來源: backend/requirements.txt)..."
pip install -r backend/requirements.txt --no-cache-dir -q # -q 靜默模式，--no-cache-dir 避免快取問題
echo "[start.sh] ✅ 後端 Python 依賴已成功安裝。"

echo "[start.sh] 正在安裝前端 Node.js 依賴 (來源: frontend/package.json)..."
# 使用子 shell ( ) 來執行 frontend 目錄下的 npm install，這樣可以避免手動 pushd/popd
# 將 npm ci 更換為 npm install 以提高容錯性
(cd frontend && npm install --verbose)
echo "[start.sh] ✅ 前端 Node.js 依賴已成功安裝。"


# --- 服務啟動 ---
if [ "$MODE" == "debug" ]; then
    # --- 除錯模式啟動流程 ---
    echo "[start.sh] 以除錯模式啟動服務 (日誌將直接輸出至此控制台)..."

    # 以後台方式啟動後端 FastAPI 服務 (在 backend 目錄下執行)
    echo "[start.sh] 啟動後端服務 (Python FastAPI)..."
    (cd backend && python main.py) &
    BACKEND_PID=$! # 獲取後端服務的進程 ID
    echo "[start.sh] ✅ 後端服務已啟動，PID: $BACKEND_PID"

    # 以後台方式啟動前端 Next.js 開發伺服器 (在 frontend 目錄下執行)
    echo "[start.sh] 啟動前端服務 (Node.js Next.js)..."
    (cd frontend && npm run dev -- -p 3000 -H 0.0.0.0) &
    FRONTEND_PID=$! # 獲取前端服務的進程 ID
    echo "[start.sh] ✅ 前端服務已啟動，PID: $FRONTEND_PID"

    echo "[start.sh] 除錯模式：等待後端 (PID: $BACKEND_PID) 和前端 (PID: $FRONTEND_PID) 進程結束..."
    echo "[start.sh] 您可以隨時在此終端使用 Ctrl+C 來手動停止所有服務。"
    # wait 命令會等待指定的背景進程結束。如果任一進程異常退出，wait 會反映其退出狀態。
    # 如果使用者 Ctrl+C，所有子進程通常也會收到 SIGINT。
    wait $BACKEND_PID $FRONTEND_PID
    echo "[start.sh] 後端和前端服務均已結束 (除錯模式)。"

else
    # --- 一般模式啟動流程 ---
    echo "[start.sh] 以一般模式在背景啟動服務 (日誌將輸出至檔案)..."

    # 使用 nohup 在背景啟動後端服務，日誌輸出到 backend.log
    # backend/main.py 的路徑是相對於專案根目錄 (即 start.sh 所在的目錄)
    echo "[start.sh] 啟動後端服務 (Python FastAPI) 並將日誌導向 backend.log..."
    nohup python backend/main.py > backend.log 2>&1 &
    echo "[start.sh] ✅ 後端服務已在背景啟動。日誌位於專案根目錄的 backend.log"

    # 使用 nohup 在背景啟動前端服務，日誌輸出到 frontend.log
    # --prefix frontend 參數讓 npm 在 frontend 目錄的上下文中執行 run dev
    echo "[start.sh] 啟動前端服務 (Node.js Next.js) 並將日誌導向 frontend.log..."
    nohup npm run dev --prefix frontend -- -p 3000 -H 0.0.0.0 > frontend.log 2>&1 &
    echo "[start.sh] ✅ 前端服務已在背景啟動。日誌位於專案根目錄的 frontend.log"

    echo "[start.sh] 一般模式：服務已在背景啟動。您可以關閉此終端，服務將繼續運行。"
    echo "[start.sh] 若要停止服務，您可能需要手動查找並結束相關的 Python 和 Node.js 進程。"
fi

echo "[start.sh] 腳本執行流程結束。"
