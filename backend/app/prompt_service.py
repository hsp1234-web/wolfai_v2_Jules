from typing import List, Dict

def build_contextual_qa_prompt(report_content: str, chat_history: List[Dict[str, str]], user_question: str) -> str:
    # 格式化聊天歷史，以便 AI 理解對話流程
    history_str_parts = []
    for msg in chat_history:
        role = msg.get('role', 'unknown') # 提供預設值以防 'role' 不存在
        content = msg.get('content', '')   # 提供預設值以防 'content' 不存在
        history_str_parts.append(f"{role.capitalize()}: {content}")
    history_str = "\n".join(history_str_parts)

    prompt = f"""你是一位專注、精確的金融分析師。你的任務是嚴格根據底下提供的「善甲狼週報內文」來回答使用者的問題。

**對話歷史:**
{history_str}

---
**善甲狼週報內文:**
```
{report_content}
```
---

**使用者最新問題:**
{user_question}

請根據以上的對話歷史和文章內文，回答使用者的最新問題。
"""
    return prompt
