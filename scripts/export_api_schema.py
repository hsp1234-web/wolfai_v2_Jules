# -*- coding: utf-8 -*-
import json
import requests
import os

# --- 腳本常量 ---
API_BASE_URL = "http://localhost:8000"  # 後端服務運行的基礎 URL
OPENAPI_ENDPOINT = f"{API_BASE_URL}/openapi.json"
OUTPUT_FILENAME = "openapi.json"       # 導出的契約檔案名稱

# 計算專案根目錄的路徑 (假設此腳本位於專案根目錄下的 scripts/ 子目錄中)
# os.path.abspath(__file__) -> /app/scripts/export_api_schema.py
# os.path.dirname(os.path.abspath(__file__)) -> /app/scripts
# os.path.dirname(os.path.dirname(os.path.abspath(__file__))) -> /app (專案根目錄)
PROJECT_ROOT_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(PROJECT_ROOT_PATH, OUTPUT_FILENAME)

def export_schema():
    """
    主函數，用於獲取 FastAPI 應用的 OpenAPI schema 並將其保存到檔案。
    """
    print(f"ℹ️  準備從 {OPENAPI_ENDPOINT} 導出 API Schema...")
    print(f"ℹ️  將導出到: {OUTPUT_PATH}")

    try:
        response = requests.get(OPENAPI_ENDPOINT, timeout=10) # 10 秒超時
        response.raise_for_status()  # 如果 HTTP 狀態碼是 4xx 或 5xx，則拋出 HTTPError

        api_schema = response.json()

        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(api_schema, f, indent=2, ensure_ascii=False)

        print(f"✅ API Schema 已成功導出至: {OUTPUT_PATH}")
        print("   您可以將此 openapi.json 檔案用於前端類型生成、API 文件化或 Postman/Insomnia 等工具。")

    except requests.exceptions.ConnectionError:
        print(f"❌ 錯誤：無法連接到後端服務於 {API_BASE_URL}。")
        print(f"   請執行以下步驟檢查：")
        print(f"   1. 確認後端 FastAPI 服務 (通常執行 'python backend/main.py' 或透過 uvicorn) 正在運行。")
        print(f"   2. 檢查服務是否監聽在預期的端口 (預設為 8000)。")
        print(f"   3. 如果在容器中運行，請確認端口映射是否正確。")
    except requests.exceptions.HTTPError as e:
        print(f"❌ 錯誤：獲取 API Schema 失敗。HTTP 狀態碼: {e.response.status_code}。")
        print(f"   URL: {OPENAPI_ENDPOINT}")
        try:
            # 嘗試打印錯誤回應的內容，可能包含有用的 FastAPI 錯誤訊息
            error_details = e.response.json()
            print(f"   錯誤詳情: {json.dumps(error_details, indent=2, ensure_ascii=False)}")
        except json.JSONDecodeError:
            print(f"   錯誤回應內容 (非 JSON): {e.response.text}")
    except requests.exceptions.Timeout:
        print(f"❌ 錯誤：連接到 {OPENAPI_ENDPOINT} 超時。請檢查服務是否響應緩慢或網路連線。")
    except requests.exceptions.RequestException as e:
        print(f"❌ 錯誤：獲取 API Schema 時發生請求相關錯誤: {e}")
    except IOError as e:
        print(f"❌ 錯誤：寫入 API Schema 到檔案 '{OUTPUT_PATH}' 時發生 IO 錯誤: {e}")
    except Exception as e:
        print(f"❌ 發生未預期錯誤: {e}")

if __name__ == "__main__":
    export_schema()
