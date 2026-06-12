"""Agent路由 — 意图匹配 + 严重度评估 + Skill Registry"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENT_DIR = os.path.join(ROOT, "agents")

def _load_jsons(d):
    if not os.path.exists(d): return []
    return [json.load(open(os.path.join(d, f), "r", encoding="utf-8")) for f in os.listdir(d) if f.endswith(".json")]

_agents = _load_jsons(AGENT_DIR)

# 严重度关键词
P0 = ["被攻击","入侵了","勒索","挖矿","webshell","被黑了","数据泄露","正在扫描"]
P1 = ["漏洞","SQL注入","XSS","RCE","提权","后门","异常进程","可疑","SSRF","XXE"]
P2 = ["OWASP","CVE","渗透","安全","攻击手法","防御","加密","注入","攻防","网络安全"]

def severity(question: str) -> dict:
    q = question.lower()
    for w in P0:
        if w.lower() in q: return {"is_security":True,"severity":"P0","reason":f"关键词:{w}"}
    for w in P1:
        if w.lower() in q: return {"is_security":True,"severity":"P1","reason":f"关键词:{w}"}
    for w in P2:
        if w.lower() in q: return {"is_security":True,"severity":"P2","reason":f"关键词:{w}"}
    return {"is_security":False,"severity":"INFO","reason":""}

def classify(question: str) -> dict:
    best, best_score = None, 0
    for a in _agents:
        score = sum(1 for kw in a.get("triggers",[]) if kw.lower() in question.lower())
        if score > best_score: best_score, best = score, a
    if not best: best = {"name":"nobody","display":"Nobody","emoji":"👤","prompt":""}
    sev = severity(question)
    best.update(sev)
    return best

def match_skills(question: str) -> list:
    from core.skills_loader import match as sk_match
    matched = sk_match(question)
    reg = __import__('core.skills_loader', fromlist=['registry']).registry()
    return [reg.get(name, {}) for name, _ in matched]
