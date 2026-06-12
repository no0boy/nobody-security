"""
Nobody — 大脑（对话引擎 v3.0）

核心变化:
  - talk() / talk_stream(): 使用 context.assemble() 动态组装上下文
  - ask() / ask_stream():  保留旧接口，内部委托给 talk()
  - LLM 延迟初始化，支持运行时重连
"""

import json
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from core.persona import name as persona_name, greeting, tone
from core.router import classify as agent_classify, match_skills
from core.context import assemble as assemble_context, AssembledContext

# ═══════════════════════════════════════════════════════════
# LLM 管理（延迟初始化 + 线程安全）
# ═══════════════════════════════════════════════════════════

_llm = None
_llm_lock = threading.Lock()


def _resolve_env(val):
    if isinstance(val, str) and val.startswith("${") and val.endswith("}"):
        return os.getenv(val[2:-1], "")
    return val


def _init_llm():
    path = os.path.join(os.path.dirname(__file__), "provider.json")
    with open(path, "r", encoding="utf-8") as f:
        p = json.load(f)
    key = _resolve_env(p.get("api_key", ""))
    if not key or len(key) < 4:
        return None
    return ChatOpenAI(
        model=p.get("model", "deepseek-chat"),
        api_key=key,
        base_url=p.get("base_url", "https://api.deepseek.com/v1"),
        temperature=0.7,
        max_tokens=2048,
    )


def get_llm():
    """获取 LLM 实例（延迟初始化，线程安全）"""
    global _llm
    if _llm is not None:
        return _llm
    with _llm_lock:
        if _llm is None:
            _llm = _init_llm()
    return _llm


def reset_llm():
    """强制重新初始化 LLM（API key 更新后调用）"""
    global _llm
    with _llm_lock:
        _llm = _init_llm()
    return _llm is not None


# ═══════════════════════════════════════════════════════════
# v3.0: talk() — 使用上下文组装引擎
# ═══════════════════════════════════════════════════════════

def talk(question: str, user_id: str = "master", project_id: str = "") -> dict:
    """
    新版对话入口：动态组装上下文。

    流程：classify → match_skills → assemble_context → LLM
    """
    agent = agent_classify(question)
    skills = match_skills(question)
    ctx = assemble_context(
        question,
        user_id=user_id,
        project_id=project_id,
        severity=agent.get("severity", "INFO"),
    )

    llm = get_llm()
    if llm is None:
        return {
            "answer": "大脑未连接。请设置 API Key。",
            "agent": agent,
            "skills": skills,
            "sources": ctx.sources,
            "debug": ctx.debug,
        }

    msg = [
        SystemMessage(content=ctx.system_prompt),
        HumanMessage(content=question),
    ]

    try:
        resp = llm.invoke(msg)
        return {
            "answer": resp.content,
            "agent": agent,
            "skills": skills,
            "sources": ctx.sources,
            "debug": ctx.debug,
        }
    except Exception as e:
        return {
            "answer": f"处理失败：{str(e)[:200]}",
            "agent": agent,
            "skills": skills,
            "sources": [],
        }


def talk_stream(question: str, user_id: str = "master", project_id: str = ""):
    """
    新版流式对话入口。
    """
    agent = agent_classify(question)
    skills = match_skills(question)
    ctx = assemble_context(
        question,
        user_id=user_id,
        project_id=project_id,
        severity=agent.get("severity", "INFO"),
    )

    # 元信息
    yield {
        "type": "agent",
        "name": agent.get("display", "Nobody"),
        "emoji": agent.get("emoji", "👤"),
        "severity": agent.get("severity", "INFO"),
        "sev_reason": agent.get("sev_reason", ""),
    }
    if skills:
        yield {
            "type": "skills",
            "skills": [
                {"name": s.get("name", ""), "display": s.get("display", "")}
                for s in skills
            ],
        }
    if ctx.debug:
        yield {"type": "debug", "layers": ctx.debug}

    llm = get_llm()
    if llm is None:
        yield {"type": "chunk", "text": "大脑未连接。"}
        yield {"type": "done", "sources": ctx.sources}
        return

    msg = [
        SystemMessage(content=ctx.system_prompt),
        HumanMessage(content=question),
    ]

    full = ""
    try:
        for chunk in llm.stream(msg):
            if chunk.content:
                full += chunk.content
                yield {"type": "chunk", "text": chunk.content}
    except Exception as e:
        full = f"错误：{str(e)[:200]}"
        yield {"type": "chunk", "text": full}

    yield {"type": "done", "sources": ctx.sources, "agent": agent}


# ═══════════════════════════════════════════════════════════
# v2.x 兼容接口（旧版 ask / ask_stream）
# ═══════════════════════════════════════════════════════════

# 旧版 SYSTEM_PROMPT（v2.3 兼容）
_LEGACY_PROMPT = """你是 {name}。{persona_prompt}
语气要求：{tone}
参考知识：{context}
规则：1.优先基于参考知识 2.不知道就说不知道 3.严格按语气要求"""


def ask(question: str, user_id: str = "guest") -> dict:
    """旧版兼容接口，内部升级为 talk()"""
    result = talk(question, user_id=user_id)
    return {
        "answer": result["answer"],
        "agent": result["agent"],
        "skills": result["skills"],
        "sources": [s.get("preview", "")[:300] for s in result.get("sources", [])],
    }


def ask_stream(question: str, user_id: str = "guest"):
    """旧版兼容接口，内部升级为 talk_stream()"""
    yield from talk_stream(question, user_id=user_id)


# ═══════════════════════════════════════════════════════════
# 多 Agent 协作（占位 / 后续扩展）
# ═══════════════════════════════════════════════════════════

def multi_agent(question: str) -> dict:
    """多 Agent 协作模式（后续版本实现）"""
    result = talk(question)
    result["agents_used"] = [result.get("agent", {}).get("display", "Nobody")]
    result["collaborative"] = False
    return result
