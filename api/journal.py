"""
日志 API — 统一事件流管理

端点:
  POST   /api/journal/entry      写入事件
  GET    /api/journal/recent     最近事件
  GET    /api/journal/timeline   时间线视图
  GET    /api/journal/memories   长期记忆视图
  GET    /api/journal/experiences  经验视图
  DELETE /api/journal/entry/{id} 删除事件
"""

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from typing import Optional
import os

from core.journal import Journal
from core.profile import Profile

router = APIRouter(prefix="/api/journal", tags=["journal"])
ADMIN_KEY = os.getenv("ADMIN_KEY", "")


def _verify_admin(x_admin: Optional[str]) -> bool:
    return x_admin is not None and x_admin == ADMIN_KEY


def _require_admin(x_admin: Optional[str] = Header(None)):
    if not _verify_admin(x_admin):
        raise HTTPException(status_code=403, detail="仅管理员可用")


# ── 模型 ──

class EntryReq(BaseModel):
    type: str = "note"
    summary: str = ""
    detail: str = ""
    tags: list = []
    project_id: str = ""
    importance: int = 0


# ── 写入 ──

@router.post("/entry")
def add_entry(req: EntryReq, x_admin: Optional[str] = Header(None)):
    """写入一条事件"""
    _require_admin(x_admin)
    if not req.summary.strip():
        return {"code": 400, "message": "summary 不能为空"}

    valid_types = ["memory", "learning", "research", "achievement", "note", "decision"]
    if req.type not in valid_types:
        return {"code": 400, "message": f"type 必须为: {', '.join(valid_types)}"}

    event_id = Journal.add(
        type=req.type,
        summary=req.summary.strip(),
        detail=req.detail.strip(),
        tags=req.tags,
        project_id=req.project_id,
        importance=req.importance,
    )
    return {"code": 0, "data": {"id": event_id}}


@router.post("/learn")
def add_learning(req: EntryReq, x_admin: Optional[str] = Header(None)):
    """快捷记录学习"""
    _require_admin(x_admin)
    event_id = Journal.learn(
        topic=req.summary, detail=req.detail, tags=req.tags
    )
    return {"code": 0, "data": {"id": event_id}}


@router.post("/remember")
def remember(req: EntryReq, x_admin: Optional[str] = Header(None)):
    """快捷保存长期记忆"""
    _require_admin(x_admin)
    event_id = Journal.remember(content=req.summary, tags=req.tags)
    return {"code": 0, "data": {"id": event_id}}


# ── 查询 ──

@router.get("/recent")
def recent(days: int = 7, limit: int = 20, x_admin: Optional[str] = Header(None)):
    """最近事件"""
    _require_admin(x_admin)
    events = Journal.recent(days=days, limit=limit)
    return {"code": 0, "data": events}


@router.get("/timeline")
def timeline(days: int = 30, x_admin: Optional[str] = Header(None)):
    """时间线视图（按日期聚合）"""
    _require_admin(x_admin)
    tl = Journal.timeline(days=days)
    return {"code": 0, "data": tl}


@router.get("/memories")
def memories(limit: int = 20, x_admin: Optional[str] = Header(None)):
    """长期记忆视图"""
    _require_admin(x_admin)
    mems = Journal.memories(limit=limit)
    return {"code": 0, "data": mems}


@router.get("/experiences")
def experiences(days: int = 30, x_admin: Optional[str] = Header(None)):
    """经验视图"""
    _require_admin(x_admin)
    exps = Journal.experiences(days=days)
    return {"code": 0, "data": exps}


# ── 删除 ──

@router.delete("/entry/{event_id}")
def delete_entry(event_id: str, x_admin: Optional[str] = Header(None)):
    """删除一条事件"""
    _require_admin(x_admin)
    from store.database import Database
    from core.journal import _get_db

    with _get_db().connect() as conn:
        conn.execute("DELETE FROM events WHERE id=?", (event_id,))
    return {"code": 0, "message": "已删除"}
