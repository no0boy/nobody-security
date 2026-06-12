"""
对话 API v3.0 — 使用上下文组装引擎

端点:
  POST /api/conversation/talk     流式对话（新）
  GET  /api/conversation/today    Today 数据
  GET  /api/conversation/welcome  欢迎信息
"""

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json
import os
from datetime import datetime

import brain
from core.memory import Memory
from core.journal import Journal
from core.profile import Profile, Preference

router = APIRouter(prefix="/api/conversation", tags=["conversation"])

ADMIN_KEY = os.getenv("ADMIN_KEY", "")
GUEST_MODE = os.getenv("GUEST_MODE", "on").lower() != "off"  # 默认开启


def _verify_admin(x_admin: Optional[str]) -> bool:
    if not x_admin or not x_admin == ADMIN_KEY:
        return False
    return True


# ── 请求模型 ──

class TalkReq(BaseModel):
    question: str
    stream: bool = True
    session_id: Optional[str] = "default"
    project_id: Optional[str] = ""


# ── 对话 ──

@router.post("/talk")
def talk(req: TalkReq, x_admin: Optional[str] = Header(None)):
    """对话入口。Master 走 LLM + 缓存；游客走缓存 → RAG 直出，零 LLM 成本。"""
    is_admin = _verify_admin(x_admin)
    if not is_admin and not GUEST_MODE:
        raise HTTPException(status_code=403, detail="游客模式已关闭，请登录管理员")
    sid = req.session_id or "default"
    Memory.session_add(sid, "user", req.question)

    if is_admin:
        return _master_talk(req, sid)
    else:
        return _guest_talk(req, sid)


def _master_talk(req: TalkReq, sid: str):
    """Master: LLM 完整对话 → 写缓存"""
    if not req.stream:
        result = brain.talk(req.question, user_id="master", project_id=req.project_id or "")
        Memory.session_add(sid, "ai", result.get("answer", "")[:500])
        result["is_admin"] = True
        # 写缓存供游客复用
        from store.cache import set as cache_set
        cache_set(req.question, result.get("answer", ""))
        return {"code": 0, "data": result}

    def generate():
        full = ""
        for event in brain.talk_stream(req.question, user_id="master", project_id=req.project_id or ""):
            if event.get("type") == "chunk":
                full += event.get("text", "")
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        # 流式结束后写缓存
        if full:
            from store.cache import set as cache_set
            cache_set(req.question, full)

    return StreamingResponse(generate(), media_type="text/event-stream")


def _guest_talk(req: TalkReq, sid: str):
    """游客: 缓存 → RAG 直出，零 LLM 成本"""
    # 1. 查缓存
    from store.cache import get as cache_get, set as cache_set
    from core.rag import search as rag_search

    cached = cache_get(req.question)
    if cached:
        Memory.session_add(sid, "ai", cached[:500])
        if not req.stream:
            return {"code": 0, "data": {
                "answer": cached, "agent": {"display": "Nobody (缓存)"},
                "skills": [], "sources": [], "is_admin": False,
            }}
        def cached_stream():
            yield f"data: {json.dumps({'type':'agent','name':'Nobody (缓存)','emoji':'👤','severity':'INFO'}, ensure_ascii=False)}\n\n"
            for i in range(0, len(cached), 50):
                yield f"data: {json.dumps({'type':'chunk','text':cached[i:i+50]}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type':'done','sources':[]}, ensure_ascii=False)}\n\n"
        return StreamingResponse(cached_stream(), media_type="text/event-stream")

    # 2. RAG 直出
    knowledge = rag_search(req.question)
    if knowledge:
        answer = f"📚 知识库检索结果：\n\n{knowledge[:1500]}"
        cache_set(req.question, answer)
        Memory.session_add(sid, "ai", answer[:500])
        if not req.stream:
            return {"code": 0, "data": {
                "answer": answer, "agent": {"display": "Nobody (知识库)"},
                "skills": [], "sources": [knowledge[:300]], "is_admin": False,
            }}
        def rag_stream():
            yield f"data: {json.dumps({'type':'agent','name':'Nobody (知识库)','emoji':'📚','severity':'INFO'}, ensure_ascii=False)}\n\n"
            for i in range(0, len(answer), 50):
                yield f"data: {json.dumps({'type':'chunk','text':answer[i:i+50]}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type':'done','sources':[knowledge[:300]]}, ensure_ascii=False)}\n\n"
        return StreamingResponse(rag_stream(), media_type="text/event-stream")

    # 3. 兜底
    fallback = "知识库中暂无相关内容。试试问：OWASP Top 10 / SQL 注入 / XSS / CVE 查询"
    if not req.stream:
        return {"code": 0, "data": {"answer": fallback, "agent": {"display": "Nobody"}, "skills": [], "sources": [], "is_admin": False}}
    def fb_stream():
        yield f"data: {json.dumps({'type':'agent','name':'Nobody','emoji':'👤','severity':'INFO'}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type':'chunk','text':fallback}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type':'done','sources':[]}, ensure_ascii=False)}\n\n"
    return StreamingResponse(fb_stream(), media_type="text/event-stream")


# ── Today ──

@router.get("/today")
def today(x_admin: Optional[str] = Header(None)):
    """Today 页面数据"""
    today_str = datetime.now().strftime("%Y-%m-%d")
    hour = datetime.now().hour
    greeting = "早上好" if hour < 12 else "下午好" if hour < 18 else "晚上好"

    is_admin = _verify_admin(x_admin)
    suggestions = []
    recent_topics = []
    goals = []
    timeline = []

    if is_admin:
        profile = Profile.all()
        prefs = Preference.all()

        # 从 Journal 取最近动态
        timeline_events = Journal.timeline(days=30, limit=10)
        timeline = [
            {"date": t["date"], "events": [e["summary"] for e in t["events"][:3]]}
            for t in timeline_events[:5]
        ]

        # 建议：从最近经验推断
        exps = Journal.experiences(days=14, limit=5)
        if exps:
            topics = list({e["summary"] for e in exps})
            recent_topics = topics[:5]
            suggestions.append(f"最近在研究：{', '.join(topics[:3])}")

        # 检查学习间隔
        learnings = Journal.query(types=["learning"], limit=10)
        if learnings:
            last_date = learnings[0].get("created_at", "")[:10] if learnings else ""
            if last_date:
                days = (datetime.now() - datetime.strptime(last_date, "%Y-%m-%d")).days
                if days >= 3:
                    suggestions.append(f"已经 {days} 天没有学习记录了，今天学点什么？")

    return {
        "code": 0,
        "data": {
            "greeting": f"{greeting}，{profile.get('name', 'no0boy')}。" if is_admin else greeting,
            "date": today_str,
            "suggestions": suggestions or ["开始今天的对话吧！"],
            "recent_topics": recent_topics,
            "goals": goals,
            "timeline": timeline,
            "is_admin": is_admin,
        },
    }


@router.get("/welcome")
def welcome(x_admin: Optional[str] = Header(None)):
    """欢迎信息"""
    is_admin = _verify_admin(x_admin)
    if is_admin:
        profile = Profile.all()
        mem_count = Journal.count()
        return {
            "code": 0,
            "data": {
                "is_admin": True,
                "profile": profile,
                "memory_count": mem_count,
            },
        }
    return {"code": 0, "data": {"is_admin": False, "msg": "游客模式 — 对话不留痕迹"}}
