"""JWT登录 + 注册（SQLite持久化）"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import jwt, JWTError
import hashlib, os, json, sqlite3
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer()

SECRET_KEY = "nobody-secret-key-2025"
USER_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "users.db")

def _user_db():
    conn = sqlite3.connect(USER_DB)
    conn.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)")
    # 默认账号
    for u, p in [("nobody","nobody2025"), ("admin","admin123")]:
        try: conn.execute("INSERT INTO users VALUES (?,?)", (u, hashlib.sha256(p.encode()).hexdigest()))
        except: pass
    conn.commit()
    return conn

def create_token(username: str) -> str:
    payload = {"sub": username, "exp": datetime.utcnow() + timedelta(hours=72)}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

class LoginReq(BaseModel):
    username: str
    password: str

@router.post("/register")
def register(req: LoginReq):
    if len(req.username) < 2 or len(req.password) < 4:
        return {"code": 400, "message": "用户名至少2字，密码至少4位"}
    db = _user_db()
    try:
        db.execute("INSERT INTO users VALUES (?,?)",
                   (req.username, hashlib.sha256(req.password.encode()).hexdigest()))
        db.commit()
        return {"code": 0, "data": {"token": create_token(req.username), "user": {"username": req.username}}}
    except sqlite3.IntegrityError:
        return {"code": 400, "message": "用户名已存在"}
    finally:
        db.close()

@router.post("/login")
def login(req: LoginReq):
    db = _user_db()
    row = db.execute("SELECT password FROM users WHERE username=?", (req.username,)).fetchone()
    db.close()
    if row and row[0] == hashlib.sha256(req.password.encode()).hexdigest():
        return {"code": 0, "data": {"token": create_token(req.username), "user": {"username": req.username}}}
    return {"code": 401, "message": "用户名或密码错误"}

def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(creds.credentials, SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub", "unknown")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token无效")
