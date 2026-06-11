"""简单JWT登录"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import jwt, JWTError
import hashlib, os, json
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer()

SECRET_KEY = "nobody-secret-key-2025"
USERS = {"admin": "admin123", "nobody": "nobody2025"}

def create_token(username: str) -> str:
    payload = {"sub": username, "exp": datetime.utcnow() + timedelta(hours=72)}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

class LoginReq(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(req: LoginReq):
    if req.username in USERS and USERS[req.username] == req.password:
        return {"code": 0, "data": {"token": create_token(req.username), "user": {"username": req.username}}}
    return {"code": 401, "message": "用户名或密码错误"}

def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(creds.credentials, SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub", "unknown")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token无效")
