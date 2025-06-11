# coding: utf-8
# # 🚀 WolfAI 終極啟動器 - 專案設定
# 請填寫您的 GitHub 專案資訊，然後點擊下一個 Code cell 上方的 ▶️ 執行按鈕。

# ## ⚙️ GitHub 倉庫與啟動腳本設定

#@markdown ### 1. GitHub 倉庫設定
#@markdown 將此處的 URL 換成您自己的專案倉庫。
REPO_URL = "https://github.com/hsp1234-web/wolfAI_v1.git" #@param {type:"string"}
#@markdown 倉庫的主要分支名稱。
REPO_BRANCH = "main" #@param {type:"string"}
#@markdown 指定將倉庫下載到 Colab 中的哪個路徑。
REPO_PATH = "/content/wolfAI_v1" #@param {type:"string"}

#@markdown ### 2. 啟動腳本設定
#@markdown 指定專案根目錄下的主要啟動腳本。
START_SCRIPT_PATH = "scripts/start.sh" #@param {type:"string"}

# ## 🛠️ 環境初始化與依賴載入
# 這個儲存格會導入必要的 Python 模組並設定一些全域變數。

import os
import subprocess
import logging
import datetime
import shlex
import json
from google.colab import userdata, drive # type: ignore

# --- 全域設定 (部分來自上方表單) ---
# REPO_URL, REPO_BRANCH, REPO_PATH, START_SCRIPT_PATH 已由表單定義
BRANCH = REPO_BRANCH # 使用表單中的分支名稱 (向下相容舊的 BRANCH 變數名)
LOG_FILE_PATH = "/content/wolfai_launcher.log"
SERVICE_ACCOUNT_JSON_PATH_IN_DRIVE = "/content/drive/MyDrive/secrets/service-account.json" # 標準路徑

EXPECTED_COLAB_SECRETS = [
    "GOOGLE_API_KEY", # 用於 Gemini
    "API_KEY_FRED",
    "API_KEY_FINMIND",
    "API_KEY_FINNHUB",
    "API_KEY_FMP",
    "ALPHA_VANTAGE_API_KEY",
    "DEEPSEEK_API_KEY",
    "GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT"
]
print("✅ 環境初始化與全域設定已載入。")

# ## 🧩 輔助函數定義
# 以下儲存格定義了腳本運行所需的各種輔助函數。

# --- 日誌設定 ---
def setup_logging():
    """設定日誌記錄器，將日誌同時輸出到控制台和檔案。"""
    try:
        # 檢查是否已經有 handlers，避免重複設定
        logger = logging.getLogger()
        if not logger.handlers: # 只在沒有 handler 時設定
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s [%(levelname)s] %(message)s",
                handlers=[
                    logging.FileHandler(LOG_FILE_PATH, mode='w', encoding='utf-8'),
                    logging.StreamHandler()
                ],
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            logging.info("日誌系統已成功設定。")
        else:
            logging.info("日誌系統先前已設定。")
    except Exception as e:
        print(f"設定日誌系統時發生錯誤: {e}")

print("🛠️ 日誌設定函數 setup_logging 已定義。")

# --- Colab Secrets 讀取 ---
def load_keys_from_colab_secrets():
    """
    從 Google Colab Secrets 中讀取 API 金鑰並設定為環境變數。
    對於 GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT，如果存在，會將其內容寫入一個暫存檔案，
    並將 GOOGLE_APPLICATION_CREDENTIALS 環境變數指向該檔案。
    """
    logging.info("正在嘗試從 Colab Secrets 載入 API 金鑰...")
    secrets_loaded_count = 0
    for key_name in EXPECTED_COLAB_SECRETS:
        try:
            value = userdata.get(key_name)
            if value: # 確保值不是空的
                if key_name == "GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT":
                    # 特殊處理服務帳號 JSON 內容
                    temp_sa_path = "/content/temp_service_account.json"
                    with open(temp_sa_path, "w") as f:
                        f.write(value)
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = temp_sa_path
                    logging.info(f"✅ 成功從 Colab Secrets 載入並設定服務帳號憑證 (來自 {key_name}) 至 {temp_sa_path}")
                    print(f"✅ 成功從 Colab Secrets 載入並設定服務帳號憑證 (來自 {key_name})")
                else:
                    os.environ[key_name] = value
                    logging.info(f"✅ 成功從 Colab Secrets 載入並設定環境變數: {key_name}")
                    print(f"✅ 成功從 Colab Secrets 載入並設定環境變數: {key_name}")
                secrets_loaded_count += 1
            else:
                logging.warning(f"⚠️ **警告**：在 Colab 密鑰中找到 {key_name}，但其值為空。相關功能可能受限。")
                print(f"⚠️ **警告**：在 Colab 密鑰中找到 {key_name}，但其值為空。相關功能可能受限。")
        except userdata.SecretNotFoundError:
            logging.warning(f"ℹ️提示：在 Colab 密鑰中未找到 {key_name}。您可以稍後在應用程式網頁介面中手動輸入 (如果需要)。")
            print(f"ℹ️提示：在 Colab 密鑰中未找到 {key_name}。您可以稍後在應用程式網頁介面中手動輸入 (如果需要)。")
        except Exception as e:
            logging.error(f"🛑 **錯誤**：讀取 Colab 密鑰 {key_name} 時發生未預期錯誤: {e}")
            print(f"🛑 **錯誤**：讀取 Colab 密鑰 {key_name} 時發生未預期錯誤: {e}")

    if secrets_loaded_count > 0:
        logging.info(f"成功從 Colab Secrets 載入 {secrets_loaded_count} 個金鑰/憑證。")
    else:
        logging.warning("未從 Colab Secrets 成功載入任何金鑰或憑證。請確保您已在 Colab 的「密鑰」分頁中設定它們。")
        print("⚠️警告：未從 Colab Secrets 成功載入任何金鑰或憑證。請確保您已在 Colab 的「密鑰」分頁中設定它們。")

print("🛠️ Colab Secrets 讀取函數 load_keys_from_colab_secrets 已定義。")

# --- 命令執行 ---
def run_command(command_str, cwd=None, shell=False):
    """
    執行給定的命令字串，並即時串流其輸出。
    如果 shell=True，則命令將通過系統的 shell 執行 (應謹慎使用)。
    """
    if not shell:
        command_list = shlex.split(command_str)
        logging.info(f"執行命令 (列表格式): {command_list} (工作目錄: {cwd or os.getcwd()})")
        print(f"\n▶️ 執行命令: {command_str}")
    else:
        command_list = command_str # 給 Popen 傳遞字串
        logging.info(f"執行命令 (Shell): {command_str} (工作目錄: {cwd or os.getcwd()})\")")
        print(f"\n▶️ 執行命令 (Shell): {command_str}")

    try:
        process = subprocess.Popen(
            command_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # Line-buffered
            universal_newlines=True,
            cwd=cwd,
            shell=shell # 允許 Popen 使用 shell
        )
        for line in process.stdout: # type: ignore
            print(line, end='') # 即時輸出到 Colab cell
            logging.info(line.strip()) # 記錄到日誌檔案
        process.wait()
        if process.returncode == 0:
            logging.info(f"命令 '{command_str}' 成功執行。")
            print(f"✅ 命令 '{command_str}' 成功執行。")
            return True
        else:
            logging.error(f"命令 '{command_str}' 執行失敗，返回碼: {process.returncode}")
            print(f"🛑 命令 '{command_str}' 執行失敗，返回碼: {process.returncode}")
            return False
    except FileNotFoundError:
        cmd_display_name = command_list[0] if isinstance(command_list, list) else command_list.split()[0]
        logging.error(f"命令 '{cmd_display_name}' 未找到。請確保相關程式已安裝且在 PATH 中。")
        print(f"🛑 命令 '{cmd_display_name}' 未找到。")
        return False
    except Exception as e:
        logging.error(f"執行命令 '{command_str}' 時發生錯誤: {e}", exc_info=True)
        print(f"🛑 執行命令 '{command_str}' 時發生錯誤: {e}")
        return False

print("🛠️ 命令執行函數 run_command 已定義。")

# --- Google Drive 與服務帳號設定 ---
def setup_google_drive_and_service_account(svc_account_json_path_in_drive):
    """掛載 Google Drive 並設定服務帳號。"""
    logging.info("開始設定 Google Drive 與服務帳號...")
    use_drive_sa = False
    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS") and os.path.exists(os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")): # type: ignore
        logging.info(f"已透過 Colab Secret 'GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT' 設定服務帳號憑證: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS')}")
        print(f"ℹ️ 已透過 Colab Secret 'GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT' 設定服務帳號憑證。")
        try:
            drive.mount('/content/drive', force_remount=True)
            logging.info("Google Drive 已成功掛載到 /content/drive (使用 Colab Secret SA)。")
            print("✅ Google Drive 已成功掛載到 /content/drive (使用 Colab Secret SA)。")
            use_drive_sa = True
        except Exception as e:
            logging.error(f"掛載 Google Drive 時發生錯誤 (即使已從 Colab Secret 載入 SA JSON): {e}", exc_info=True)
            print(f"🛑 掛載 Google Drive 時發生錯誤 (即使已從 Colab Secret 載入 SA JSON): {e}")
            print("將嘗試檢查 Drive 中的 'secrets/service-account.json' 路徑...")

    if not use_drive_sa:
        logging.info(f"正在檢查 Google Drive 中的服務帳號檔案: {svc_account_json_path_in_drive}")
        print(f"\nℹ️ 正在檢查 Google Drive 中的服務帳號檔案: {svc_account_json_path_in_drive} (此為可選的進階功能，用於持久模式))")
        try:
            drive.mount('/content/drive', force_remount=True)
            logging.info("Google Drive 已成功掛載到 /content/drive。")
            print("✅ Google Drive 已成功掛載到 /content/drive。")
            if os.path.exists(svc_account_json_path_in_drive):
                try:
                    with open(svc_account_json_path_in_drive, 'r') as f_sa:
                        json.load(f_sa) # Validate JSON
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = svc_account_json_path_in_drive
                    logging.info(f"已設定 GOOGLE_APPLICATION_CREDENTIALS 環境變數為: {svc_account_json_path_in_drive}")
                    print(f"✅ 服務帳號檔案 '{svc_account_json_path_in_drive}' 找到並已設定為 GOOGLE_APPLICATION_CREDENTIALS。")
                    use_drive_sa = True
                except json.JSONDecodeError:
                    logging.error(f"🛑 錯誤：位於 '{svc_account_json_path_in_drive}' 的檔案不是一個有效的 JSON 檔案。請檢查檔案內容。")
                    print(f"🛑 錯誤：位於 '{svc_account_json_path_in_drive}' 的檔案不是一個有效的 JSON 檔案。")
                except Exception as e_sa_read:
                    logging.error(f"🛑 讀取或解析服務帳號檔案 '{svc_account_json_path_in_drive}' 時出錯: {e_sa_read}")
                    print(f"🛑 讀取或解析服務帳號檔案 '{svc_account_json_path_in_drive}' 時出錯: {e_sa_read}")
            else:
                logging.warning(f"未在 '{svc_account_json_path_in_drive}' 找到服務帳號檔案。如果您打算使用需要 Google Drive 持久儲存的進階功能 (如排程器)，請上傳服務帳號金鑰至該路徑。基礎功能仍可運作。")
                print(f"⚠️ 提示：未在 '{svc_account_json_path_in_drive}' 找到服務帳號檔案。基礎功能仍可運作。")
        except Exception as e:
            logging.error(f"掛載 Google Drive 或檢查服務帳號檔案時發生錯誤: {e}", exc_info=True)
            print(f"🛑 掛載 Google Drive 或檢查服務帳號檔案時發生錯誤: {e}")
            print("   這可能是因為您未授權 Colab 存取 Google Drive，或者 Drive API 暫時出現問題。")
            print("   如果您不需要持久模式的進階功能，可以忽略此訊息。")
    logging.info("Google Drive 與服務帳號設定完畢。")

print("🛠️ Google Drive 與服務帳號設定函數 setup_google_drive_and_service_account 已定義。")

# ## ⚙️ 主要工作流程
# 這個儲存格定義了核心的 `main_workflow` 函數，它協調所有設定和啟動步驟。

# --- 主要工作流程 ---
def main_workflow():
    """執行主要的啟動流程。"""
    logging.info("主工作流程開始...")
    print("\n🚀 正在啟動 WolfAI v5.0 Colab 環境...")

    # 1. 從 Colab Secrets 載入 API 金鑰
    load_keys_from_colab_secrets()

    # 2. 設定 Google Drive 和服務帳號
    setup_google_drive_and_service_account(SERVICE_ACCOUNT_JSON_PATH_IN_DRIVE)

    # 3. 克隆或更新程式碼倉庫
    logging.info(f"正在處理程式碼倉庫: {REPO_URL}, 分支: {REPO_BRANCH}")
    print(f"\n🔄 正在準備程式碼倉庫 (來源: {REPO_URL}, 分支: {REPO_BRANCH})...")
    if os.path.exists(REPO_PATH) and os.path.isdir(os.path.join(REPO_PATH, ".git")):
        logging.info(f"倉庫目錄 '{REPO_PATH}' 已存在，嘗試更新...")
        print(f"   倉庫目錄 '{REPO_PATH}' 已存在，嘗試更新...")
        run_command(f"git stash push -u", cwd=REPO_PATH)
        run_command(f"git fetch origin {REPO_BRANCH}", cwd=REPO_PATH)
        run_command(f"git checkout {REPO_BRANCH}", cwd=REPO_PATH)
        run_command(f"git reset --hard origin/{REPO_BRANCH}", cwd=REPO_PATH)
        run_command("git clean -dfx", cwd=REPO_PATH)
    else:
        logging.info(f"倉庫目錄 '{REPO_PATH}' 不存在或不是 Git 倉庫，執行克隆...")
        print(f"   倉庫目錄 '{REPO_PATH}' 不存在，執行克隆...")
        if not run_command(f"git clone --branch {REPO_BRANCH} {REPO_URL} {REPO_PATH}"):
            logging.critical("克隆倉庫失敗，無法繼續。請檢查 URL、分支名稱和網路連線。")
            print("🛑 克隆倉庫失敗，無法繼續。請檢查 URL、分支名稱和網路連線。")
            return

    # 4. 安裝依賴套件
    requirements_path = os.path.join(REPO_PATH, "backend", "requirements.txt")
    logging.info(f"準備安裝依賴套件: {requirements_path}")
    print(f"\n🐍 正在安裝必要的 Python 套件 (來源: {requirements_path})...\")")
    if os.path.exists(requirements_path):
        if not run_command("pip install --upgrade pip"):
            logging.critical("升級 pip 失敗。請檢查網路連線。")
            print("🛑 升級 pip 失敗。")
            # Do not return here, try to install requirements anyway
        if not run_command(f"pip install -r {requirements_path}"):
            logging.critical("安裝依賴套件失敗。請檢查 requirements.txt 檔案和網路連線。")
            print("🛑 安裝依賴套件失敗。")
            # Do not return here, maybe some parts of app can still run
    else:
        logging.error(f"找不到依賴文件: {requirements_path}。跳過安裝步驟。")
        print(f"🛑 找不到依賴文件: {requirements_path}。跳過安裝步驟。")

    # 5. 啟動應用程式
    resolved_start_script_path = os.path.join(REPO_PATH, START_SCRIPT_PATH)
    logging.info(f"準備啟動應用程式 (腳本: {resolved_start_script_path})\")")
    print(f"\n🚀 正在嘗試啟動 WolfAI 後端服務 (腳本: {resolved_start_script_path})...")

    if os.path.exists(resolved_start_script_path):
        run_command(f"chmod +x {resolved_start_script_path}")
        print("   後端服務將在背景啟動。請監控下方的日誌輸出。")
        print("   當您看到類似 'Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)' 的訊息時，")
        print("   並且出現一個 '***** Colab Public URL: https://*.trycloudflare.com *****' 的網址時，")
        print("   表示服務已成功啟動。您可以使用該 Public URL 存取 WolfAI 網頁介面。")
        print("   如果長時間未出現 Public URL，請檢查日誌是否有錯誤訊息。")
        if not run_command(f"{resolved_start_script_path}", cwd=REPO_PATH, shell=True): # shell=True is important here
            logging.error("啟動腳本執行時遇到問題。請查看上面的日誌輸出以獲取詳細資訊。")
            print("🛑 啟動腳本執行時遇到問題。請查看上面的日誌輸出以獲取詳細資訊。")
        else:
            logging.info("啟動腳本已成功執行 (或已在背景開始執行)。")
            print("✅ 啟動腳本已成功執行 (或已在背景開始執行)。")
            print("   請耐心等待幾分鐘，讓服務完全啟動並生成公開網址。")
            print(f"   您可以查看日誌檔案 {LOG_FILE_PATH} 以獲取更詳細的啟動資訊。")
    else:
        logging.critical(f"找不到啟動腳本: {resolved_start_script_path}。無法啟動應用程式。")
        print(f"🛑 找不到啟動腳本: {resolved_start_script_path}。無法啟動應用程式。")

    logging.info("主工作流程結束。")

print("🛠️ 主要工作流程函數 main_workflow 已定義。")

# ## ▶️ 執行啟動器
# 這是腳本的執行入口。執行此儲存格將開始 WolfAI 的啟動過程。
# **請確保您已執行了前面的所有設定和函數定義儲存格。**

# --- 腳本主執行部分 ---
if __name__ == "__main__":
    try:
        # 1. 設定日誌
        setup_logging() # 確保日誌已設定

        start_time = datetime.datetime.now()
        logging.info(f"WolfAI v5.0 終極啟動器手動觸發執行於 {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🚀 WolfAI v5.0 終極啟動器開始執行於 {start_time.strftime('%Y-%m-%d %H:%M:%S')}...")
        print(f"   日誌將保存在: {LOG_FILE_PATH}")
        print("="*50)

        # 2. 執行主要工作流程
        main_workflow()

        end_time = datetime.datetime.now()
        duration = end_time - start_time
        logging.info(f"WolfAI v5.0 終極啟動器執行完畢於 {end_time.strftime('%Y-%m-%d %H:%M:%S')}。總耗時: {duration}")
        print("="*50)
        print(f"✅ WolfAI v5.0 終極啟動器執行完畢於 {end_time.strftime('%Y-%m-%d %H:%M:%S')}。")
        print(f"   總耗時: {duration}")
        print(f"   請檢查上面的輸出，特別是 Colab Public URL。")
        print("\n🎉🎉🎉 WolfAI 啟動腳本執行完畢 🎉🎉🎉")
        print(f"詳細日誌請參考: {LOG_FILE_PATH}")
        print("如果一切順利，應用程式應該已經啟動。請檢查輸出尋找公開的 URL。")

    except NameError as ne:
        # This case should ideally not happen in a script if all functions are defined globally before this block
        print(f"🛑 執行錯誤: {ne}。這通常表示腳本結構有問題，或者必要的函數未正確定義。")
        if 'logging' in globals() and logging.getLogger().handlers:
            logging.error(f"NameError: {ne}。必要函數未定義。")
    except Exception as e_global:
        error_message = f"啟動器在執行主要部分時發生未處理的嚴重錯誤: {e_global}"
        # Check if logging is available and initialized
        logger = logging.getLogger()
        if logger.handlers and logger.handlers[0].stream is not None : # type: ignore
             logging.critical(error_message, exc_info=True)
        else:
             # Fallback print if logging is not working
             print(f"啟動器日誌設定可能失敗或尚未初始化。{error_message}")
        print(f"🛑 {error_message}")
        print(f"   如果日誌系統已啟動，請檢查日誌檔案 {LOG_FILE_PATH} 以獲取詳細資訊。")
