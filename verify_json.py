import json

file_path = "run_in_colab_v5.ipynb"
try:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    json.loads(content)
    print(f"檔案 '{file_path}' 的 JSON 格式正確。")
except json.JSONDecodeError as e:
    print(f"檔案 '{file_path}' 的 JSON 格式錯誤：{e}")
    raise
except FileNotFoundError:
    print(f"檔案 '{file_path}' 未找到。")
    raise
except Exception as e:
    print(f"驗證檔案 '{file_path}' 時發生未預期錯誤：{e}")
    raise
