"""
响应缓存 — 游客复用 Master 对话结果

- Admin 对话后自动写缓存
- 游客先查缓存，命中直接返回
- 缓存 key 用问题归一化
- 最多 500 条，超出淘汰最旧的
"""

from collections import OrderedDict
import re

MAX_SIZE = 500
_cache: OrderedDict[str, dict] = OrderedDict()


def _normalize(text: str) -> str:
    """问题归一化：去空格、去标点、小写"""
    t = text.strip().lower()
    t = re.sub(r'[？?！!。，,、\s]+', ' ', t)
    return t.strip()


def get(question: str) -> str | None:
    """查缓存，返回答案或 None"""
    key = _normalize(question)
    if key in _cache:
        # 移到末尾（LRU）
        _cache.move_to_end(key)
        return _cache[key]["answer"]
    return None


def set(question: str, answer: str):
    """写缓存"""
    key = _normalize(question)
    if key in _cache:
        _cache.move_to_end(key)
        _cache[key] = {"question": question, "answer": answer}
    else:
        if len(_cache) >= MAX_SIZE:
            _cache.popitem(last=False)  # 淘汰最旧的
        _cache[key] = {"question": question, "answer": answer}


def stats() -> dict:
    return {"size": len(_cache), "max": MAX_SIZE}
