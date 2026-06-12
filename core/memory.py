"""
三层记忆系统
  core.db     — Master 核心记忆（人格/目标/项目）
  knowledge.db — Master 知识库（笔记/Payload/Writeup/CVE）
  session      — 游客对话缓存（内存，关网页清空）
"""
import json, os, sqlite3
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

    # ====== 学习记录（Master 对话时自动记录） ======
    @staticmethod
    def learn(topic):
        keywords = ["SQL注入","XSS","SSRF","RCE","提权","渗透","红队","漏洞","CVE",
                    "OWASP","Burp","Nmap","Linux","WAF","应急","CTF","靶场","防御","加密"]
        for w in keywords:
            if w in topic:
                Memory.know_set(f"learned_{w}", {"topic": w, "last": datetime.now().isoformat()})
                break
