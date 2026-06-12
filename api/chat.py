"""Nobody 聊天接口 — 游客/管理员双模式

权限：所有写入操作验证 X-Admin header，密码通过环境变量 ADMIN_KEY 注入"""
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import brain
from core.memory import Memory
from core.planner import check as planner_check

router = APIRouter(prefix="/api/chat", tags=["chat"])

ADMIN_KEY = os.getenv("ADMIN_KEY", "")  # 必须通过环境变量注入，默认禁用管理员功能

# 防暴力破解 — 限速
_admin_attempts: dict[str, list[float]] = {}

def _check_rate(ip: str, limit: int = 5) -> bool:
    now = time.time()
    if ip not in _admin_attempts:
        _admin_attempts[ip] = []
    _admin_attempts[ip] = [t for t in _admin_attempts[ip] if now - t < 60]
    if len(_admin_attempts[ip]) >= limit:
        return False
    _admin_attempts[ip].append(now)
    return True

def _verify_admin(x_admin: Optional[str], ip: str = "unknown") -> bool:
    """验证管理员身份，包含限流"""
    if not x_admin or x_admin != ADMIN_KEY:
        return False
    return _check_rate(ip, 10)  # 管理员操作每分钟10次

class AskReq(BaseModel):
    question: str
    stream: bool = True
    session_id: Optional[str] = "default"
    admin: Optional[bool] = False

@router.get("/welcome")
def welcome(request = None, x_admin: Optional[str] = Header(None)):
    is_admin = _verify_admin(x_admin)
    if is_admin:
        core = Memory.core_get()
        recent = list((Memory.know_get() or {}).keys())[-5:]
        return {"code": 0, "data": {"is_admin": True, "core_memory": core, "recent_knowledge": recent}}

    return {"code": 0, "data": {"is_admin": False, "msg": "游客模式 — 对话不留痕迹"}}

@router.get("/planner")
def planner(x_admin: Optional[str] = Header(None)):
    if not _verify_admin(x_admin):
        return {"code": 0, "data": {"suggestions": ["登录管理员后可查看学习规划。"]}}
    return {"code": 0, "data": planner_check("nobody")}


@router.get("/today")
def today(x_admin: Optional[str] = Header(None)):
    """Today 页面数据：问候 + 建议 + 目标 + 时间线"""
    from datetime import datetime
    today_str = datetime.now().strftime("%Y-%m-%d")
    hour = datetime.now().hour

    greeting = "早上好" if hour < 12 else "下午好" if hour < 18 else "晚上好"

    is_admin = _verify_admin(x_admin)
    suggestions = []
    goals = []
    recent = []
    timeline = []

    if is_admin:
        p = planner_check("nobody")
        suggestions = p.get("suggestions", [])[:3]
        recent = p.get("recent_topics", [])[:5]
        goals = p.get("goals", [])[:3]

        core = Memory.core_get() or {}
        timeline = sorted(
            [(k, v) for k, v in core.items() if isinstance(v, dict) and v.get("time")],
            key=lambda x: str(x[1].get("time", "")), reverse=True
        )[:5]
        timeline = [{"date": str(v.get("time", ""))[:10], "event": k, "detail": str(v.get("content", ""))[:100]} for k, v in timeline]

    profile = {}
    if is_admin:
        profile = Memory.get("nobody", "profile", "base") or {}

    return {"code": 0, "data": {
        "greeting": f"{greeting}，{profile.get('name', 'no0boy')}。",
        "date": today_str,
        "suggestions": suggestions or ["开始记录今天的学习吧！"],
        "recent_topics": recent,
        "goals": goals,
        "timeline": timeline,
        "is_admin": is_admin,
    }}

@router.post("/remember")
def remember(req: AskReq, x_admin: Optional[str] = Header(None)):
    """Master 主动存储记忆 —— 限流保护"""
    if not _verify_admin(x_admin):
        return {"code": 403, "message": "仅管理员可用"}

    q = req.question.strip()
    if q.startswith("记住 "):
        content = q[3:]
        Memory.core_set(f"note_{len(Memory.core_get())}", {"content": content, "time": str(__import__('datetime').datetime.now())})
        return {"code": 0, "message": f"已存储到核心记忆：{content[:50]}"}
    if q.startswith("知识 "):
        content = q[3:]
        Memory.know_set(f"kb_{len(Memory.know_get())}", {"content": content, "time": str(__import__('datetime').datetime.now())})
        return {"code": 0, "message": f"已存储到知识库：{content[:50]}"}
    return {"code": 400, "message": "格式：'记住 xxx' 或 '知识 xxx'"}

@router.get("/memory/semantic")
def sem_search(q: str = "", x_admin: Optional[str] = Header(None)):
    """语义搜索记忆"""
    if not q: return {"code": 0, "data": []}
    results = Memory.sem_search(q)
    return {"code": 0, "data": results}

@router.post("/memory/index")
def sem_index(x_admin: Optional[str] = Header(None)):
    """重建语义索引"""
    if not _verify_admin(x_admin): return {"code": 403, "message": "仅管理员"}
    Memory.sem_index()
    return {"code": 0, "message": "索引已重建"}

@router.get("/knowledge/tree")
def know_tree(x_admin: Optional[str] = Header(None)):
    """知识树"""
    tree = Memory.know_tree()
    return {"code": 0, "data": tree}

@router.post("/knowledge/add")
def know_add(req: AskReq, x_admin: Optional[str] = Header(None)):
    """按路径添加知识"""
    if not _verify_admin(x_admin): return {"code": 403, "message": "仅管理员"}
    # 格式: "路径: security/sqli/payload 内容"
    q = req.question.strip()
    if ":" in q:
        path, content = q.split(":", 1)
        Memory.know_add(path.strip(), content.strip())
        return {"code": 0, "message": f"已添加: {path.strip()}"}
    return {"code": 400, "message": "格式: 路径: 内容"}

@router.post("/ask")
def chat_ask(req: AskReq, x_admin: Optional[str] = Header(None)):
    is_admin = _verify_admin(x_admin)
    sid = req.session_id or "default"

    # 游客加会话缓存（多轮上下文），关网页清空
    Memory.session_add(sid, "user", req.question)

    if not req.stream:
        result = brain.ask(req.question)
        Memory.session_add(sid, "ai", result.get("answer", "")[:500])
        result["is_admin"] = is_admin
        # 日常交流不自动写入长期记忆，管理员通过 管理后台 或 /remember 接口主动存储
        return {"code": 0, "data": result}

    def generate():
        history = Memory.session_get(sid)
        # 把最近对话上下文注入（可选，简单版不注入）
        for event in brain.ask_stream(req.question):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
