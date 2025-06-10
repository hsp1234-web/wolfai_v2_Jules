# WolfAI 專案啟動指南

歡迎使用 WolfAI 專案！本文件將引導您如何透過 Google Colab 快速啟動並執行本專案。

---

## 🚀 快速啟動 (Quick Start)

我們提供兩種方式啟動本專案，請**擇一即可**。

### 方式一：點擊徽章 (推薦)
此為最簡單的方式。點擊下方徽章，將直接在 Google Colab 中為您開啟預設的啟動器。

[![在 Colab 中開啟](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/hsp1234-web/wolfAI_v1/blob/main/run_in_colab.ipynb)

### 方式二：手動複製 (進階使用者)
1. 前往 [Google Colab](https://colab.research.google.com/) 並建立一個新的筆記本。
2. 點擊下方摺疊區塊，複製內部所有程式碼。
3. 將程式碼貼到您新建立的 Colab 儲存格中，設定好選項後執行。

<details>
<summary>▶️ <strong>點此展開/摺疊程式碼</strong></summary>

```python
#@title wolfAI_v1 智慧型啟動器 (v2.0)
#@markdown ---
#@markdown ### **步驟 1: 請選擇執行選項**
#@markdown 請完成以下設定，然後點擊左側的 ▶️ **執行按鈕**來啟動程式。
#@markdown
#@markdown **執行模式**:
#@markdown - `正常`: 為一般使用者設計，提供最穩定、簡潔的啟動流程。
#@markdown - `除錯`: 為開發者設計，將輸出詳細日誌並執行一系列自動化系統健康檢查。
execution_mode = "正常" #@param ["正常", "除錯"]
#@markdown
#@markdown ---
#@markdown ### **步驟 2: (可選) 掛載 Google Drive**
#@markdown **是否掛載雲端硬碟**:
#@markdown - `否`: 標準模式，程式將在臨時環境中運行，關閉後資料不會保留。
#@markdown - `是`: 如果您需要讀取或永久保存資料到您的 Google Drive，請選擇此項。
mount_drive_option = "否" #@param ["是", "否"]
#@markdown ---

# --- 模組導入 ---
import os
import subprocess
import logging
from datetime import datetime

# --- 常數設定 ---
REPO_URL = "https://github.com/hsp1234-web/wolfAI_v1.git"
REPO_PATH = "/content/wolfAI_v1"
LOG_DIR = "/content/logs"
BRANCH = "main" # 固定使用 main 分支

def setup_logging():
    """設定日誌記錄器，根據執行模式決定日誌級別"""
    os.makedirs(LOG_DIR, exist_ok=True)
    log_filename = os.path.join(LOG_DIR, f"wolfai_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

    log_level = logging.DEBUG if execution_mode == '除錯' else logging.INFO

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler()
        ]
    )
    logging.info(f"日誌級別設定為: {'DEBUG' if log_level == logging.DEBUG else 'INFO'}")
    logging.info(f"日誌檔案將儲存於: {log_filename}")

def run_command(command, cwd=None):
    """安全地執行 Shell 命令並串流輸出日誌"""
    logging.info(f"執行命令: `{' '.join(command)}` (於 {cwd or os.getcwd()})")
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            cwd=cwd
        )
        for line in iter(process.stdout.readline, ''):
            if line:
                logging.info(line.strip())
        process.stdout.close()
        return_code = process.wait()
        if return_code:
            raise subprocess.CalledProcessError(return_code, command)
        logging.info(f"命令成功完成: `{' '.join(command)}`")
    except Exception as e:
        logging.error(f"命令執行失敗: `{' '.join(command)}`，錯誤: {e}")
        raise

def main_workflow():
    """執行完整的工作流程"""
    # 1. 掛載雲端硬碟 (如果使用者選擇)
    if mount_drive_option == "是":
        try:
            from google.colab import drive
            logging.info("使用者選擇掛載 Google Drive...")
            drive.mount('/content/drive')
            logging.info("Google Drive 掛載成功於 /content/drive")
        except Exception as e:
            logging.error(f"Google Drive 掛載失敗: {e}")
            return # 掛載失敗則終止流程
    else:
        logging.info("使用者選擇不掛載 Google Drive，跳過此步驟。")

    # 2. 克隆或更新程式碼倉庫
    logging.info("--- 正在準備程式碼倉庫 ---")
    try:
        if not os.path.exists(REPO_PATH):
            run_command(['git', 'clone', '--branch', BRANCH, REPO_URL, REPO_PATH])
        else:
            logging.info("倉庫已存在，正在更新...")
            run_command(['git', 'fetch', '--all'], cwd=REPO_PATH)
            run_command(['git', 'reset', '--hard', f'origin/{BRANCH}'], cwd=REPO_PATH)
            run_command(['git', 'pull'], cwd=REPO_PATH)
        logging.info("程式碼倉庫準備完成。")
    except Exception as e:
        logging.critical("準備程式碼倉庫時發生嚴重錯誤，流程中止。")
        return

    # 3. 安裝依賴套件
    logging.info("--- 正在安裝依賴套件 ---")
    try:
        requirements_path = os.path.join(REPO_PATH, 'backend', 'requirements.txt')
        if os.path.exists(requirements_path):
            run_command(['pip', 'install', '-r', requirements_path])
            logging.info("依賴套件安裝完成。")
        else:
            raise FileNotFoundError("找不到 requirements.txt 檔案！")
    except Exception as e:
        logging.critical("安裝依賴時發生嚴重錯誤，流程中止。")
        return

    # 4. 執行系統健康檢查 (僅在除錯模式)
    if execution_mode == "除錯":
        logging.info("--- [除錯模式] 執行系統健康檢查 ---")
        try:
            backend_path = os.path.join(REPO_PATH, 'backend')
            run_command(['pip', 'install', 'pytest'])
            run_command(['pytest'], cwd=backend_path)
            logging.info("系統健康檢查完成。")
        except Exception as e:
            logging.warning(f"系統健康檢查出現問題: {e}") # 測試失敗不應中止主流程

    # 5. 啟動服務
    logging.info("--- 正在啟動應用程式服務 ---")
    try:
        start_script_path = os.path.join(REPO_PATH, 'scripts', 'start.sh')
        if os.path.exists(start_script_path):
            run_command(['chmod', '+x', start_script_path])
            logging.info("正在背景啟動服務，請查看日誌以獲取詳細資訊。")

            env = os.environ.copy()
            env['OPERATION_MODE'] = execution_mode.upper()

            log_file = os.path.join(LOG_DIR, "services.log")
            cmd = f"nohup {start_script_path} > {log_file} 2>&1 &"
            subprocess.Popen(cmd, shell=True, env=env, cwd=REPO_PATH)

            logging.info(f"服務已在背景啟動。您可以透過以下命令查看即時日誌：\n!tail -f {log_file}")
            print(f"\n✅ 系統啟動指令已發送！請稍待幾分鐘讓服務完全上線。")
            print(f"👉 您可以使用 `!tail -f {log_file}` 來追蹤服務啟動進度。")

        else:
            raise FileNotFoundError("找不到 start.sh 啟動腳本！")
    except Exception as e:
        logging.critical(f"啟動服務時發生嚴重錯誤: {e}")
        return

# --- 執行主流程 ---
if __name__ == "__main__":
    setup_logging()
    logging.info(f"=== WolfAI v2.0 智慧型啟動器開始執行 ===")
    logging.info(f"選擇模式: {execution_mode}, 是否掛載Drive: {mount_drive_option}")
    try:
        main_workflow()
        logging.info("=== 智慧型啟動器流程執行完畢 ===")
    except Exception as e:
        logging.critical(f"主流程遭遇未處理的例外狀況: {e}")
        logging.info("=== 智慧型啟動器因錯誤而中止 ===")
```

</details>

-----

## ⚙️ 運作原理詳解 (How It Works)

本節將詳細說明啟動器背後的程式邏輯與除錯機制。

### 程式主要邏輯

啟動器會依序執行以下步驟：

1.  **環境設定**：腳本頂端的表單讓使用者可以選擇`執行模式`和`是否掛載雲端硬碟`。這些選擇會作為變數，控制後續流程。
2.  **掛載雲端硬碟**：程式會檢查`是否掛載雲端硬碟`選項。如果為`是`，則呼叫 Google Colab 的 `drive.mount()`函式，並請求您的授權，將您的雲端硬碟掛載到 `/content/drive` 路徑。
3.  **準備程式碼**：程式會檢查 `/content/wolfAI_v1` 目錄是否存在。如果不存在，會從 GitHub `git clone` 主分支 (`main`) 的最新程式碼；如果已存在，則會執行 `git pull` 來確保程式碼是最新版本。
4.  **安裝依賴套件**：程式會尋找 `backend/requirements.txt` 檔案，並使用 `pip install -r` 命令來安裝所有後端服務所需的 Python 套件。
5.  **啟動服務**：程式會執行 `scripts/start.sh` 腳本。這個腳本負責在背景分別啟動 FastAPI 後端伺服器和 Next.js 前端應用程式，並將它們的日誌分別導向 `backend.log` 和 `frontend.log`。

### 除錯模式 (Debug Mode) 邏輯

當您選擇「除錯」模式時，除了上述步驟外，還會額外執行以下操作：

1.  **啟用詳細日誌**：日誌系統的記錄級別會從 `INFO` 調整為 `DEBUG`，這意味著終端機會印出更詳細、更頻繁的執行狀態，幫助開發者追蹤問題。
2.  **執行自動化測試**：在安裝完依賴套件後，程式會額外使用 `pip` 安裝 `pytest` 測試框架，然後在 `backend` 目錄下執行 `pytest` 命令，對所有 API 和服務進行自動化單元測試，並印出測試報告。
