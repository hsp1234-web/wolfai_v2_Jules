import pytest
from typing import List, Dict
import sys
import os

# 將 backend/app 目錄添加到 sys.path
APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'app'))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from prompt_service import build_contextual_qa_prompt # noqa: E402

# 測試案例的參數化列表
TEST_CASES = [
    (
        "這是週報的內容。",
        [],
        "使用者第一個問題是什麼？",
        """你是一位專注、精確的金融分析師。你的任務是嚴格根據底下提供的「善甲狼週報內文」來回答使用者的問題。

**對話歷史:**


---
**善甲狼週報內文:**
```
這是週報的內容。
```
---

**使用者最新問題:**
使用者第一個問題是什麼？

請根據以上的對話歷史和文章內文，回答使用者的最新問題。
"""
    ),
    (
        "關於市場波動的分析報告。",
        [
            {"role": "user", "content": "你好"},
            {"role": "model", "content": "你好，有什麼可以幫您的嗎？"}
        ],
        "市場前景如何？",
        """你是一位專注、精確的金融分析師。你的任務是嚴格根據底下提供的「善甲狼週報內文」來回答使用者的問題。

**對話歷史:**
User: 你好
Model: 你好，有什麼可以幫您的嗎？

---
**善甲狼週報內文:**
```
關於市場波動的分析報告。
```
---

**使用者最新問題:**
市場前景如何？

請根據以上的對話歷史和文章內文，回答使用者的最新問題。
"""
    ),
    (
        "另一份週報內容。",
        [
            {"role": "user", "content": "請解釋名詞A。"},
            {"role": "model", "content": "名詞A的解釋是..."},
            {"role": "user", "content": "那名詞B呢？"}
        ],
        "與名詞A有何不同？",
        """你是一位專注、精確的金融分析師。你的任務是嚴格根據底下提供的「善甲狼週報內文」來回答使用者的問題。

**對話歷史:**
User: 請解釋名詞A。
Model: 名詞A的解釋是...
User: 那名詞B呢？

---
**善甲狼週報內文:**
```
另一份週報內容。
```
---

**使用者最新問題:**
與名詞A有何不同？

請根據以上的對話歷史和文章內文，回答使用者的最新問題。
"""
    ),
    # 測試聊天歷史中缺少 role 或 content 的情況
    (
        "週報內容C。",
        [
            {"content": "只有內容，沒有角色。"}, # 缺少 role
            {"role": "model"} # 缺少 content
        ],
        "這個怎麼處理？",
        """你是一位專注、精確的金融分析師。你的任務是嚴格根據底下提供的「善甲狼週報內文」來回答使用者的問題。

**對話歷史:**
Unknown: 只有內容，沒有角色。
Model:

---
**善甲狼週報內文:**
```
週報內容C。
```
---

**使用者最新問題:**
這個怎麼處理？

請根據以上的對話歷史和文章內文，回答使用者的最新問題。
"""
    )
]

@pytest.mark.parametrize("report_content, chat_history, user_question, expected_prompt", TEST_CASES)
def test_build_contextual_qa_prompt(
    report_content: str,
    chat_history: List[Dict[str, str]],
    user_question: str,
    expected_prompt: str
):
    """測試 build_contextual_qa_prompt 函數是否能根據不同的輸入正確生成提示詞。"""
    prompt = build_contextual_qa_prompt(report_content, chat_history, user_question)
    assert prompt == expected_prompt

# 可以添加更多特定邊界條件的測試，如果需要的話
# 例如，空的報告內容、空的用戶問題等，但目前的 parametrize 應該涵蓋了主要 logique
if __name__ == '__main__':
    # 方便直接執行此文件進行測試 (雖然推薦使用 pytest 命令)
    pytest.main(['-v', __file__])
