"""
Nobody — Security Partner 大脑（协调器）
脑模块: core/persona | core/memory | core/rag | core/router | core/planner
"""

import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from core.persona import name as persona_name, greeting, tone
from core.memory import Memory
from core.rag import search as rag_search, init_knowledge
from core.router import classify as agent_classify, match_skills
from core.planner import check as planner_check

# ========== 模型初始化 ==========

_llm = None

def _resolve_env(val):
    if isinstance(val, str) and val.startswith("${") and val.endswith("}"):
        return os.getenv(val[2:-1], "")
    return val

def _init_llm():
    global _llm
    path = os.path.join(os.path.dirname(__file__), "provider.json")
    with open(path, "r", encoding="utf-8") as f:
        p = json.load(f)
    key = _resolve_env(p.get("api_key", ""))
    if not key or len(key) < 4:
        _llm = None; return
    _llm = ChatOpenAI(model=p.get("model","deepseek-chat"), api_key=key,
                      base_url=p.get("base_url","https://api.deepseek.com/v1"),
                      temperature=0.7, max_tokens=2048)

_init_llm()

# ========== 核心问答 ==========

SYSTEM_PROMPT = """你是 {name}。{persona_prompt}
语气要求：{tone}
参考知识：{context}
规则：1.优先基于参考知识 2.不知道就说不知道 3.严格按语气要求"""

def ask(question: str, user_id: str = "guest") -> dict:
    agent = agent_classify(question)
    skills = match_skills(question)
    context = rag_search(question)

    msg = [SystemMessage(content=SYSTEM_PROMPT.format(
        name=persona_name(), persona_prompt=agent.get("prompt",""),
        tone=tone(agent.get("severity","INFO")), context=context or "无"
    ))]
    msg.append(HumanMessage(content=question))

    if _llm is None: return {"answer": "大脑未连接。","agent":agent,"skills":skills,"sources":[]}
    try:
        resp = _llm.invoke(msg)
        return {"answer": resp.content, "agent": agent, "skills": skills, "sources": [context[:300]] if context else []}
    except Exception as e:
        return {"answer": f"处理失败：{str(e)[:200]}", "agent": agent, "skills": skills, "sources": []}

def ask_stream(question: str, user_id: str = "guest"):
    agent = agent_classify(question)
    skills = match_skills(question)
    context = rag_search(question)

    yield {"type":"agent","name":agent.get("display","Nobody"),"emoji":agent.get("emoji","👤"),
           "severity":agent.get("severity","INFO"),"sev_reason":agent.get("sev_reason","")}
    if skills:
        yield {"type":"skills","skills":[{"name":s.get("name",""),"display":s.get("display","")} for s in skills]}

    msg = [SystemMessage(content=SYSTEM_PROMPT.format(
        name=persona_name(), persona_prompt=agent.get("prompt",""),
        tone=tone(agent.get("severity","INFO")), context=context or "无"
    ))]
    msg.append(HumanMessage(content=question))

    if _llm is None:
        yield {"type":"chunk","text":"大脑未连接。"}; yield {"type":"done","sources":[]}; return

    full = ""
    try:
        for chunk in _llm.stream(msg):
            if chunk.content: full += chunk.content; yield {"type":"chunk","text":chunk.content}
    except Exception as e:
        full = f"错误：{str(e)[:200]}"; yield {"type":"chunk","text":full}
    yield {"type":"done","sources":[context[:300]] if context else [],"agent":agent}

# ========== 多Agent协作 ==========

def multi_agent(question: str) -> dict:
    agent = agent_classify(question)
    agents_to_run = [agent]
    if agent.get("severity") in ("P0","P1"):
        for a in []:  # TODO: 从 agents/ 配置中按 severity 匹配协作 Agent
            pass
    result = ask(question)
    result["agents_used"] = [agent.get("display","")]
    result["collaborative"] = False
    return result
