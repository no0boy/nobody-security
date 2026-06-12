"""Nobody 身份 — 单用户，不需要登录"""
from fastapi import Depends
from fastapi.security import HTTPBearer
from jose import jwt

SECRET = "nobody-secret-2025"
security = HTTPBearer(auto_error=False)

def get_current_user(creds=None):
    """Nobody 只有一个用户"""
    return "nobody"

def create_token():
    return jwt.encode({"sub": "nobody"}, SECRET, algorithm="HS256")
