"""主动规划 — 学习提醒 + 建议"""
from datetime import datetime
from core.memory import Memory

ROADMAP = {
    "SQL注入": ["XSS","命令注入","SSRF"],
    "XSS": ["CSRF","CORS","DOM XSS"],
    "提权": ["Linux提权","Windows提权","AD域提权"],
    "渗透": ["信息收集","漏洞扫描","漏洞利用","后渗透"],
}

def check(user_id: str) -> dict:
    learning = Memory.get(user_id, "learning") or {}
    goals = Memory.get(user_id, "goals") or {}

    days_since = 999
    for k, v in learning.items():
        try:
            last_date = datetime.strptime(v.get("last","")[:10], "%Y-%m-%d")
            days = (datetime.now() - last_date).days
            if days < days_since: days_since = days
        except: pass

    suggestions = []
    if days_since >= 3:
        recent = list(learning.keys())[-3:] if learning else []
        if recent: suggestions.append(f"你已经 {days_since} 天没学了。上次：{', '.join(recent)}，继续？")

    for topic in list(learning.keys())[-3:]:
        if topic in ROADMAP:
            for nt in ROADMAP[topic]:
                if nt not in learning:
                    suggestions.append(f"🎯 学完 {topic} 后建议学 {nt}")
                    break

    return {
        "days_since_last": days_since,
        "suggestions": suggestions[:3],
        "recent_topics": list(learning.keys())[-5:] if learning else [],
        "goals": list(goals.keys())[:3] if goals else [],
    }
