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

def classify(question: str) -> dict:
    """匹配最合适的Agent"""
    best = None
    best_score = 0
    for agent in _agents:
        score = sum(1 for kw in agent.get("triggers", []) if kw.lower() in question.lower())
        if score > best_score:
            best_score = score
            best = agent
    return best or {"name": "nobody", "display": "Nobody", "emoji": "💀", "prompt": _persona.get("voice", {}).get("greeting", "Nobody 在线。")}

def match_skills(question: str) -> list:
    """匹配相关技能"""
    matched = []
    for skill in _skills:
        score = sum(1 for kw in skill.get("triggers", []) if kw.lower() in question.lower())
        if score > 0:
            matched.append(skill)
    return matched

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

    yield {"type": "agent", "name": agent.get("display", "Nobody"), "emoji": agent.get("emoji", "💀")}

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
