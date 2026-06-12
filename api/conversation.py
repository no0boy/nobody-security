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
    """新版流式对话（使用上下文组装引擎）"""
    is_admin = _verify_admin(x_admin)
    user_id = "master" if is_admin else "guest"
    sid = req.session_id or "default"

    Memory.session_add(sid, "user", req.question)

    if not req.stream:
        result = brain.talk(req.question, user_id=user_id, project_id=req.project_id or "")
        Memory.session_add(sid, "ai", result.get("answer", "")[:500])
        result["is_admin"] = is_admin
        return {"code": 0, "data": result}

    def generate():
        for event in brain.talk_stream(
            req.question,
            user_id=user_id,
            project_id=req.project_id or "",
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


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
