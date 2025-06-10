import json

file_path = "openapi.json"

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        openapi_content = json.load(f)

    if "paths" in openapi_content:
        new_paths = {}
        for path, path_item in openapi_content["paths"].items():
            if path.startswith("/api/"):
                new_path = f"/api/v1{path[len('/api'):]}"
                new_paths[new_path] = path_item
            else:
                new_paths[path] = path_item
        openapi_content["paths"] = new_paths
    else:
        print("警告：openapi.json 檔案中未找到 'paths' 物件。")

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(openapi_content, f, ensure_ascii=False, indent=2)

    print(f"檔案 '{file_path}' 已成功修改，API 路徑已添加 /v1 前綴。")

except FileNotFoundError:
    print(f"錯誤：檔案 '{file_path}' 未找到。")
    raise
except json.JSONDecodeError as e:
    print(f"錯誤：解析檔案 '{file_path}' 的 JSON 時發生錯誤：{e}")
    raise
except Exception as e:
    print(f"處理檔案 '{file_path}' 時發生未預期錯誤：{e}")
    raise
