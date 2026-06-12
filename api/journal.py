"""
日志 API — 统一事件流管理

所有敏感端点受 ADMIN_KEY 保护，写入端自带限流防暴力破解。
"""

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import os
import time

from core.journal import Journal

router = APIRouter(prefix="/api/journal", tags=["journal"])
ADMIN_KEY = os.getenv("ADMIN_KEY", "")

# ── 防暴力破解限流 ──
_rate_buckets: dict[str, list[float]] = {}

def _check_rate(ip: str, limit: int = 10) -> bool:
    now = time.time()
    bucket = _rate_buckets.setdefault(ip, [])
    bucket[:] = [t for t in bucket if now - t < 60]
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True


# ── 鉴权 ──

def _verify_admin(x_admin: Optional[str], request: Request) -> bool:
    """验证管理员 + 限流"""
    if not x_admin or x_admin != ADMIN_KEY:
        return False
    ip = request.client.host if request.client else "unknown"
    return _check_rate(ip, 10)


def _require_admin(x_admin: Optional[str] = Header(None), request: Request = None):
    if not _verify_admin(x_admin, request):
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
def add_entry(req: EntryReq, x_admin: Optional[str] = Header(None), request: Request = None):
    _require_admin(x_admin, request)
    if not req.summary.strip():
        return {"code": 400, "message": "summary 不能为空"}
    event_id = Journal.add(
        type=req.type, summary=req.summary.strip(),
        detail=req.detail.strip(), tags=req.tags,
        project_id=req.project_id, importance=req.importance,
    )
    return {"code": 0, "data": {"id": event_id}}


@router.post("/learn")
def add_learning(req: EntryReq, x_admin: Optional[str] = Header(None), request: Request = None):
    _require_admin(x_admin, request)
    event_id = Journal.learn(topic=req.summary, detail=req.detail, tags=req.tags)
    return {"code": 0, "data": {"id": event_id}}


@router.post("/remember")
def remember(req: EntryReq, x_admin: Optional[str] = Header(None), request: Request = None):
    _require_admin(x_admin, request)
    event_id = Journal.remember(content=req.summary, tags=req.tags)
    return {"code": 0, "data": {"id": event_id}}


# ── 查询 ──

@router.get("/recent")
def recent(days: int = 7, limit: int = 20, x_admin: Optional[str] = Header(None), request: Request = None):
    _require_admin(x_admin, request)
    return {"code": 0, "data": Journal.recent(days=days, limit=limit)}


@router.get("/timeline")
def timeline(days: int = 30, x_admin: Optional[str] = Header(None), request: Request = None):
    _require_admin(x_admin, request)
    return {"code": 0, "data": Journal.timeline(days=days)}


@router.get("/memories")
def memories(limit: int = 20, x_admin: Optional[str] = Header(None), request: Request = None):
    _require_admin(x_admin, request)
    return {"code": 0, "data": Journal.memories(limit=limit)}


@router.get("/experiences")
def experiences(days: int = 30, x_admin: Optional[str] = Header(None), request: Request = None):
    _require_admin(x_admin, request)
    return {"code": 0, "data": Journal.experiences(days=days)}


# ── 删除（软删除，可恢复）──

@router.delete("/entry/{event_id}")
def delete_entry(event_id: str, x_admin: Optional[str] = Header(None), request: Request = None):
    _require_admin(x_admin, request)
    from core.journal import _get_db
    with _get_db().connect() as conn:
        conn.execute("UPDATE events SET confirmed = -1 WHERE id = ?", (event_id,))
    return {"code": 0, "message": "已归档（软删除）"}
