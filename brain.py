"""
Nobody — Security Partner 核心大脑
v1.0 : 加载配置 → 意图匹配 → RAG检索 → LLM生成
"""

import json
import os
import sys

# 加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from datetime import datetime
import sqlite3

# ========== 五维记忆系统 ==========

MEMORY_DB = os.path.join(os.path.dirname(__file__), "memory.db")

def _mem_db():
    conn = sqlite3.connect(MEMORY_DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS memories (
        user_id TEXT, type TEXT, key TEXT, value TEXT,
        updated_at TEXT, PRIMARY KEY (user_id, type, key))""")
    return conn

class Memory:
    """👤个人档案 ❤️偏好 📚学习 💼经验 🎯目标"""

    @staticmethod
    def set(user_id, mem_type, key, value):
        db = _mem_db()
        db.execute("INSERT OR REPLACE INTO memories VALUES (?,?,?,?,?)",
                   (user_id, mem_type, key, json.dumps(value, ensure_ascii=False),
                    datetime.now().isoformat()))
        db.commit(); db.close()

    @staticmethod
    def get(user_id, mem_type, key=None):
        db = _mem_db()
        if key:
            row = db.execute("SELECT value FROM memories WHERE user_id=? AND type=? AND key=?",
                             (user_id, mem_type, key)).fetchone()
            db.close()
            return json.loads(row[0]) if row else None
        rows = db.execute("SELECT key, value FROM memories WHERE user_id=? AND type=?",
                          (user_id, mem_type)).fetchall()
        db.close()
        return {r[0]: json.loads(r[1]) for r in rows}

    @staticmethod
    def welcome(user_id):
        p = Memory.get(user_id, "profile", "base") or {}
        if not p:
            return {"is_new": True, "msg": "👤 Nobody 在线。你是谁？\n告诉我：称呼,方向,水平\n例：「no0boy,红队,入门」"}
        learn = list((Memory.get(user_id, "learning") or {}).keys())[-5:]
        goals = list((Memory.get(user_id, "goals") or {}).keys())[:3]
        return {"is_new": False, "profile": p,
                "recent": learn, "goals": goals,
                "msg": f"👤 {p.get('name','')}，欢迎回来。\n📚 最近：{', '.join(learn) if learn else '暂无'}\n🎯 目标：{', '.join(goals) if goals else '未设定'}"}

    @staticmethod
    def try_parse(user_id, text):
        if Memory.get(user_id, "profile", "base"): return None
        parts = text.replace("，",",").replace("、",",").split(",")
        if len(parts) >= 2:
            p = {"name": parts[0].strip(), "direction": parts[1].strip(),
                 "level": parts[2].strip() if len(parts) > 2 else "入门"}
            Memory.set(user_id, "profile", "base", p)
            return p
        return None

    @staticmethod
    def record(user_id, question):
        for w in ["SQL注入","XSS","SSRF","RCE","提权","渗透","红队","蓝队","漏洞","CVE",
                  "OWASP","Burp","Nmap","Linux","Python","WAF","日志","应急","CTF","靶场",
                  "代码审计","防御","加密","免杀","社工","内网","域控"]:
            if w in question:
                Memory.set(user_id, "learning", w,
                          {"last": datetime.now().isoformat()})
                break

# ========== 加载配置 ==========

def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

_persona = _load_json(os.path.join(os.path.dirname(__file__), "persona.json"))
_provider = _load_json(os.path.join(os.path.dirname(__file__), "provider.json"))

AGENT_DIR = os.path.join(os.path.dirname(__file__), "agents")
SKILL_DIR = os.path.join(os.path.dirname(__file__), "skills")

def _load_jsons(directory):
    """加载目录下所有json文件"""
    if not os.path.exists(directory):
        return []
    return [_load_json(os.path.join(directory, f)) for f in os.listdir(directory) if f.endswith(".json")]

_agents = _load_jsons(AGENT_DIR)
_skills = _load_jsons(SKILL_DIR)

# ========== 初始化模型 ==========

_llm = None

def _init_llm():
    global _llm
    key = _provider.get("api_key", os.getenv("DASHSCOPE_API_KEY", ""))
    if not key or len(key) < 4:
        _llm = None
        return
    _llm = ChatOpenAI(
        model=_provider.get("model", "deepseek-chat"),
        api_key=key,
        base_url=_provider.get("base_url", "https://api.deepseek.com/v1"),
        temperature=0.7,
        max_tokens=2048
    )

_init_llm()

# ========== 意图匹配 ==========

def assess_severity(question: str) -> dict:
    """安全事件严重度评估 — 关键词 + LLM 双重判断"""
    # 关键词快速通道：省一次 LLM 调用
    p0_words = ["被攻击", "入侵了", "勒索", "挖矿", "webshell", "被黑了", "数据泄露", "正在扫描"]
    p1_words = ["漏洞", "SQL注入", "XSS", "RCE", "提权", "后门", "异常进程", "可疑", "SSRF", "XXE"]
    p2_words = ["OWASP", "CVE", "渗透", "安全", "攻击手法", "防御", "加密", "注入", "攻防"]

    q_lower = question.lower()
    for w in p0_words:
        if w.lower() in q_lower:
            return {"is_security": True, "severity": "P0", "reason": f"关键词匹配：{w}"}
    for w in p1_words:
        if w.lower() in q_lower:
            return {"is_security": True, "severity": "P1", "reason": f"关键词匹配：{w}"}
    for w in p2_words:
        if w.lower() in q_lower:
            return {"is_security": True, "severity": "P2", "reason": f"关键词匹配：{w}"}

    return {"is_security": False, "severity": "INFO", "reason": ""}


def classify(question: str) -> dict:
    """匹配最合适的Agent + 严重度评估"""
    best = None
    best_score = 0
    for agent in _agents:
        score = sum(1 for kw in agent.get("triggers", []) if kw.lower() in question.lower())
        if score > best_score:
            best_score = score
            best = agent

    if best is None:
        best = {"name": "nobody", "display": "Nobody", "emoji": "👤", "prompt": _persona.get("voice", {}).get("greeting", "Nobody 在线。")}

    # 安全事件评估
    sev = assess_severity(question)
    best["severity"] = sev.get("severity", "INFO")
    best["sev_reason"] = sev.get("reason", "")
    best["is_security"] = sev.get("is_security", False)

    return best

def match_skills(question: str) -> list:
    """匹配相关技能并执行工具函数"""
    matched = []
    for skill in _skills:
        score = sum(1 for kw in skill.get("triggers", []) if kw.lower() in question.lower())
        if score > 0:
            s = {**skill, "score": score}
            # 执行技能的工具（如果有）
            tools_result = []
            for tool_name in skill.get("tools", []):
                fn = _get_tool_fn(tool_name)
                if fn:
                    try:
                        tools_result.append(fn(question))
                    except Exception:
                        pass
            s["tools_result"] = tools_result
            matched.append(s)
    matched.sort(key=lambda x: x.get("score", 0), reverse=True)
    return matched


def _get_tool_fn(name: str):
    """工具函数注册表 — 映射工具名到函数"""
    import urllib.request, json as _json

    def cve_lookup(q):
        try:
            kw = q.split()[-1] if q.split() else q
            url = f"https://cve.circl.lu/api/cve/{kw}"
            req = urllib.request.Request(url, headers={"User-Agent": "Nobody/1.0"})
            resp = urllib.request.urlopen(req, timeout=3)
            data = _json.loads(resp.read().decode())
            return f"CVE-{kw}: {data.get('summary', '无描述')[:200]}"
        except Exception:
            return None

    def sqli_detect(q):
        indicators = ["'", "\"", "OR 1=1", "UNION SELECT", "--"]
        found = [i for i in indicators if i.lower() in q.lower()]
        return f"检测到SQL注入特征：{', '.join(found)}" if found else "未检测到明显SQL注入特征"

    _tools = {
        "cve_lookup": cve_lookup,
        "sqli_detect": sqli_detect,
    }
    return _tools.get(name)

# ========== RAG 检索 ==========

def _rag_search(question: str) -> str:
    """从知识库检索相关内容"""
    import chromadb
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    persist_dir = os.path.join(os.path.dirname(__file__), "chroma_data")
    client = chromadb.PersistentClient(path=persist_dir)
    collection = client.get_or_create_collection(name="nobody_knowledge")

    try:
        # 简单关键词检索（v1.0 不用 embedding API，纯关键词）
        results = collection.get(include=["documents", "metadatas"])
        if not results["documents"]:
            return ""

        keywords = question.lower().split()
        matches = []
        for doc in results["documents"]:
            score = sum(1 for kw in keywords if kw in doc.lower())
            if score > 0:
                matches.append((score, doc))

        matches.sort(key=lambda x: x[0], reverse=True)
        return "\n---\n".join([d[:500] for _, d in matches[:3]])
    except Exception:
        return ""

# ========== 知识库初始化 ==========

def init_knowledge():
    """启动时检查知识库，空则导入种子文档"""
    import chromadb

    persist_dir = os.path.join(os.path.dirname(__file__), "chroma_data")
    client = chromadb.PersistentClient(path=persist_dir)
    collection = client.get_or_create_collection(name="nobody_knowledge")

    if collection.count() > 0:
        return

    seeds_dir = os.path.join(os.path.dirname(__file__), "knowledge", "seeds")
    if not os.path.exists(seeds_dir):
        return

    print("[Nobody] 知识库为空，导入种子文档...")
    count = 0
    for f in os.listdir(seeds_dir):
        fp = os.path.join(seeds_dir, f)
        if not f.endswith((".txt", ".md")):
            continue
        with open(fp, "r", encoding="utf-8") as fh:
            text = fh.read()
        # 简单切片
        chunks = [text[i:i+500] for i in range(0, len(text), 500)]
        for j, chunk in enumerate(chunks):
            collection.add(
                ids=[f"{f}_chunk_{j}"],
                documents=[chunk],
                metadatas=[{"source": f, "chunk": j}]
            )
            count += 1
    print(f"[Nobody] 已导入 {count} 个知识片段")

# ========== 核心问答 ==========

SYSTEM_PROMPT = """你是 {name}（{display}）。
{persona_prompt}

知识库参考：
{context}

回答规则：
1. 优先基于参考知识回答
2. 知识库里没有的，诚实告知
3. 风格：{style}
"""

def ask(question: str) -> dict:
    """核心问答流程"""
    agent = classify(question)
    skills = match_skills(question)
    context = _rag_search(question)

    # 构建 Prompt
    persona_prompt = agent.get("prompt", _persona.get("voice", {}).get("greeting", ""))
    system = SYSTEM_PROMPT.format(
        name=_persona["name"],
        display=agent.get("display", "Nobody"),
        persona_prompt=persona_prompt,
        context=context if context else "（知识库中暂无相关内容）",
        style=_persona.get("style", "直接")
    )

    messages = [SystemMessage(content=system)]
    messages.append(HumanMessage(content=question))

    # 调大模型
    if _llm is None:
        return {
            "answer": "Nobody 大脑未连接。请配置 provider.json 中的 API Key。",
            "agent": agent,
            "skills": skills,
            "sources": []
        }

    try:
        response = _llm.invoke(messages)
        Memory.record("nobody", question)  # 记下学习内容
        return {
            "answer": response.content,
            "agent": agent,
            "skills": skills,
            "sources": [context[:300]] if context else []
        }
    except Exception as e:
        return {
            "answer": f"处理失败：{str(e)[:200]}",
            "agent": agent,
            "skills": skills,
            "sources": []
        }

def ask_stream(question: str):
    """流式问答"""
    agent = classify(question)
    skills = match_skills(question)
    context = _rag_search(question)

    persona_prompt = agent.get("prompt", "")
    system = SYSTEM_PROMPT.format(
        name=_persona["name"],
        display=agent.get("display", "Nobody"),
        persona_prompt=persona_prompt,
        context=context if context else "（知识库中暂无相关内容）",
        style=_persona.get("style", "直接")
    )

    messages = [SystemMessage(content=system)]
    messages.append(HumanMessage(content=question))

    yield {"type": "agent", "name": agent.get("display", "Nobody"), "emoji": agent.get("emoji", "👤"),
           "severity": agent.get("severity", "INFO"), "sev_reason": agent.get("sev_reason", "")}
    if skills:
        yield {"type": "skills", "skills": [{"name": s.get("name",""), "display": s.get("display","")} for s in skills]}

    if _llm is None:
        yield {"type": "chunk", "text": "Nobody 大脑未连接。"}
        yield {"type": "done", "sources": []}
        return

    full = ""
    try:
        for chunk in _llm.stream(messages):
            if chunk.content:
                full += chunk.content
                yield {"type": "chunk", "text": chunk.content}
    except Exception as e:
        full = f"处理失败：{str(e)[:200]}"
        yield {"type": "chunk", "text": full}

    yield {"type": "done", "sources": [context[:300]] if context else [], "agent": agent}
