from typing import Dict, Any

async def get_ai_reply(prompt: str, api_key: str, selected_model: str) -> Dict[str, Any]:
    """
    模擬 AI 服務的回應。

    在 V1.0 中，這個函數只返回一個固定的假資料或基於輸入的簡單處理，
    以便前端和聊天 API 可以整合。
    實際的 AI 模型調用將在後續版本中實現。
    """
    print(f"[Mock AI Service] 接收到請求:\n    模型: {selected_model}\n    API 金鑰 (前5碼): {api_key[:5]}...\n    提示詞 (前50字): {prompt[:50]}...")

    # 模擬處理延遲
    # import asyncio
    # await asyncio.sleep(0.5) # 模擬0.5秒的網絡延遲和處理時間

    # 根據請求中的某些信息構造一個稍微動態的模擬回覆
    mock_reply_content = f"已收到您的提示。如果我是真實的 '{selected_model}' 模型，我會根據以下提示來處理您的請求: '{prompt[:100]}...' (使用 API 金鑰 '{api_key[:5]}...'). 這是一個模擬回覆。"

    return {"reply": mock_reply_content, "model_used": selected_model, "status": "mock_success"}

# 如果需要，可以添加一個同步版本，以防某些測試或調用不方便使用 async
def get_ai_reply_sync(prompt: str, api_key: str, selected_model: str) -> Dict[str, Any]:
    """同步版本的模擬 AI 服務回應。"""
    print(f"[Mock AI Service - Sync] 接收到請求:\n    模型: {selected_model}\n    API 金鑰 (前5碼): {api_key[:5]}...\n    提示詞 (前50字): {prompt[:50]}...")
    mock_reply_content = f"(同步)已收到您的提示。如果我是真實的 '{selected_model}' 模型，我會處理: '{prompt[:100]}...' (API金鑰 '{api_key[:5]}...'). 模擬回覆。"
    return {"reply": mock_reply_content, "model_used": selected_model, "status": "mock_success_sync"}
