"""
身份 API — Master Profile + Preferences

所有敏感端点受 ADMIN_KEY 保护，写入端自带限流。
"""

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import os
import time

from core.profile import Profile, Preference

router = APIRouter(prefix="/api/profile", tags=["profile"])
ADMIN_KEY = os.getenv("ADMIN_KEY", "")

# ── 限流 ──
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
    if not x_admin or x_admin != ADMIN_KEY:
        return False
    ip = request.client.host if request.client else "unknown"
    return _check_rate(ip, 10)

def _require_admin(x_admin: Optional[str] = Header(None), request: Request = None):
    if not _verify_admin(x_admin, request):
        raise HTTPException(status_code=403, detail="仅管理员可用")

# ── 模型 ──

class ProfileUpdate(BaseModel):
    key: str
    value: str

# ── Profile ──

@router.get("")
def get_profile(x_admin: Optional[str] = Header(None), request: Request = None):
    _require_admin(x_admin, request)
    return {"code": 0, "data": {
        "profile": Profile.all(),
        "summary": Profile.identity_summary(),
    }}

@router.put("")
def update_profile(req: ProfileUpdate, x_admin: Optional[str] = Header(None), request: Request = None):
    _require_admin(x_admin, request)
    if not req.key.strip():
        return {"code": 400, "message": "key 不能为空"}
    Profile.set(req.key.strip(), req.value.strip())
    return {"code": 0, "message": f"已更新: {req.key}"}

@router.post("/init")
def init_profile(req: ProfileUpdate, x_admin: Optional[str] = Header(None), request: Request = None):
    _require_admin(x_admin, request)
    Profile.set(req.key.strip(), req.value.strip())
    return {"code": 0, "message": f"已设置: {req.key} = {req.value}"}

# ── Preference ──

@router.get("/preferences")
def get_preferences(x_admin: Optional[str] = Header(None), request: Request = None):
    _require_admin(x_admin, request)
    return {"code": 0, "data": {
        "preferences": Preference.all(),
        "summary": Preference.summary(),
    }}

@router.put("/preferences")
def update_preference(req: ProfileUpdate, x_admin: Optional[str] = Header(None), request: Request = None):
    _require_admin(x_admin, request)
    if not req.key.strip():
        return {"code": 400, "message": "key 不能为空"}
    Preference.set(req.key.strip(), req.value.strip())
    return {"code": 0, "message": f"偏好已更新: {req.key}"}
