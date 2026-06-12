"""
三层记忆系统 + 知识树 + 语义搜索
  core.db     — Master 核心记忆（人格/目标/项目）
  knowledge.db — Master 知识库（支持路径: security/sqli/payload.txt）
  session      — 游客对话缓存（内存，关网页清空）
  sem_search   — ChromaDB 语义搜索记忆
"""
import json, os, sqlite3, chromadb
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE_DB = os.path.join(ROOT, "memory_core.db")
KNOW_DB = os.path.join(ROOT, "memory_knowledge.db")

# 会话缓存（内存，不持久化）
_session_store: dict[str, list[dict]] = {}

def _db(path):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS mem (key TEXT PRIMARY KEY, value TEXT, updated TEXT)")
    return conn

class Memory:
    # ====== 通用读写（兼容 goals 等新类型） ======
    @staticmethod
    def get(user_id, mem_type, key=None):
        if mem_type == "goals":
            return Memory.core_get()  # goals 存在 memory_core.db
        if mem_type in ("profile","preference","learning","experience"):
            if key: return Memory.core_get(key)
            return {k:v for k,v in (Memory.core_get() or {}).items() if not k.startswith("note_")}
        if mem_type == "knowledge":
            return Memory.know_get(key)
        return {}

    @staticmethod
    def set(user_id, mem_type, key, value):
        if mem_type in ("goals", "profile", "preference", "learning", "experience"):
            Memory.core_set(key, value)
        elif mem_type == "knowledge":
            Memory.know_set(key, value)

    # ====== 核心记忆（Master 才写） ======
    @staticmethod
    def core_set(key, value):
        db = _db(CORE_DB)
        db.execute("INSERT OR REPLACE INTO mem VALUES (?,?,?)",
                   (key, json.dumps(value, ensure_ascii=False), datetime.now().isoformat()))
        db.commit(); db.close()

    @staticmethod
    def core_get(key=None):
        db = _db(CORE_DB)
        if key:
            row = db.execute("SELECT value FROM mem WHERE key=?", (key,)).fetchone()
            db.close(); return json.loads(row[0]) if row else None
        rows = db.execute("SELECT key,value FROM mem").fetchall()
        db.close(); return {r[0]: json.loads(r[1]) for r in rows}

    # ====== 知识记忆（Master 才写） ======
    @staticmethod
    def know_set(key, value):
        db = _db(KNOW_DB)
        db.execute("INSERT OR REPLACE INTO mem VALUES (?,?,?)",
                   (key, json.dumps(value, ensure_ascii=False), datetime.now().isoformat()))
        db.commit(); db.close()

    @staticmethod
    def know_get(key=None):
        db = _db(KNOW_DB)
        if key:
            row = db.execute("SELECT value FROM mem WHERE key=?", (key,)).fetchone()
            db.close(); return json.loads(row[0]) if row else None
        rows = db.execute("SELECT key,value FROM mem").fetchall()
        db.close(); return {r[0]: json.loads(r[1]) for r in rows}

    # ====== 会话缓存（游客和Master都可用，关网页清空） ======
    @staticmethod
    def session_add(session_id, role, content):
        if session_id not in _session_store:
            _session_store[session_id] = []
        _session_store[session_id].append({"role": role, "content": content, "time": datetime.now().isoformat()})
        # 只保留最近 20 轮
        if len(_session_store[session_id]) > 20:
            _session_store[session_id] = _session_store[session_id][-20:]

    @staticmethod
    def session_get(session_id):
        return _session_store.get(session_id, [])

    # ====== 知识树 ======
    @staticmethod
    def know_tree():
        """返回知识树结构"""
        tree = {}
        all_items = Memory.know_get() or {}
        for key, val in all_items.items():
            # key 格式: "security/sqli/payload" 或 "kb_0" (旧格式)
            parts = key.split("/") if "/" in key else ["_other", key]
            node = tree
            for part in parts[:-1]:
                if part not in node: node[part] = {}
                node = node[part]
            node[parts[-1]] = str(val)[:100] if isinstance(val, dict) else str(val)[:100]
        return tree

    @staticmethod
    def know_add(path, content):
        """按路径添加知识: knowledge/security/sqli/payload"""
        Memory.know_set(path, {"content": content, "time": datetime.now().isoformat()})

    # ====== 语义记忆搜索 ======
    @staticmethod
    def sem_index():
        """将核心记忆索引到 ChromaDB 用于语义搜索"""
        from core.rag import _embed_text
        persist = os.path.join(os.path.dirname(ROOT), "chroma_data")
        client = chromadb.PersistentClient(path=persist)
        col = client.get_or_create_collection(name="nobody_memory", metadata={"hnsw:space": "cosine"})

        items = Memory.core_get() or {}
        cnt = 0
        for key, val in items.items():
            text = f"{key}: {json.dumps(val, ensure_ascii=False)}"
            try:
                emb = _embed_text(text)
                col.upsert(ids=[key], embeddings=[emb], documents=[text])
                cnt += 1
            except: pass
        print(f"[Memory] 语义索引已重建，共 {cnt} 条")
        return cnt

    @staticmethod
    def sem_search(query: str, top_k: int = 5) -> list:
        """语义搜索记忆 — 中文Embedding"""
        try:
            from core.rag import _embed_text
            persist = os.path.join(os.path.dirname(ROOT), "chroma_data")
            col = chromadb.PersistentClient(path=persist).get_or_create_collection(name="nobody_memory")
            emb = _embed_text(query)
            results = col.query(query_embeddings=[emb], n_results=top_k, include=["documents"])
            return results["documents"][0] if results["documents"] else []
        except: return []

    # ====== 学习记录 ======
    @staticmethod
    def learn(topic):
        keywords = ["SQL注入","XSS","SSRF","RCE","提权","渗透","红队","漏洞","CVE",
                    "OWASP","Burp","Nmap","Linux","WAF","应急","CTF","靶场","防御","加密"]
        for w in keywords:
            if w in topic:
                Memory.know_set(f"learned_{w}", {"topic": w, "last": datetime.now().isoformat()})
                break
