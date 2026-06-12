"""
身份 API — Master Profile + Preferences

端点:
  GET  /api/profile            获取全部身份信息
  PUT  /api/profile            更新身份
  GET  /api/profile/preferences  获取偏好
  PUT  /api/profile/preferences  更新偏好
"""

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from typing import Optional
import os

from core.profile import Profile, Preference

router = APIRouter(prefix="/api/profile", tags=["profile"])
ADMIN_KEY = os.getenv("ADMIN_KEY", "")


def _verify_admin(x_admin: Optional[str]) -> bool:
    return x_admin is not None and x_admin == ADMIN_KEY


def _require_admin(x_admin: Optional[str] = Header(None)):
    if not _verify_admin(x_admin):
        raise HTTPException(status_code=403, detail="仅管理员可用")


# ── 模型 ──

class ProfileUpdate(BaseModel):
    key: str
    value: str


class PreferenceUpdate(BaseModel):
    key: str
    value: str


# ── Profile ──

@router.get("")
def get_profile(x_admin: Optional[str] = Header(None)):
    """获取 Master 身份"""
    _require_admin(x_admin)
    return {
        "code": 0,
        "data": {
            "profile": Profile.all(),
            "summary": Profile.identity_summary(),
        },
    }


@router.put("")
def update_profile(req: ProfileUpdate, x_admin: Optional[str] = Header(None)):
    """更新 Master 身份字段"""
    _require_admin(x_admin)
    if not req.key.strip():
        return {"code": 400, "message": "key 不能为空"}
    Profile.set(req.key.strip(), req.value.strip())
    return {"code": 0, "message": f"已更新: {req.key}"}


@router.post("/init")
def init_profile(req: ProfileUpdate, x_admin: Optional[str] = Header(None)):
    """
    初始化 Master 身份（首次使用）
    接受 JSON body: { key: "name", value: "no0boy" }
    可多次调用设置不同字段
    """
    _require_admin(x_admin)
    Profile.set(req.key.strip(), req.value.strip())
    return {"code": 0, "message": f"已设置: {req.key} = {req.value}"}


# ── Preference ──

@router.get("/preferences")
def get_preferences(x_admin: Optional[str] = Header(None)):
    """获取全部偏好（含默认值）"""
    _require_admin(x_admin)
    return {
        "code": 0,
        "data": {
            "preferences": Preference.all(),
            "summary": Preference.summary(),
        },
    }


@router.put("/preferences")
def update_preference(req: PreferenceUpdate, x_admin: Optional[str] = Header(None)):
    """更新偏好"""
    _require_admin(x_admin)
    if not req.key.strip():
        return {"code": 400, "message": "key 不能为空"}
    Preference.set(req.key.strip(), req.value.strip())
    return {"code": 0, "message": f"偏好已更新: {req.key}"}
