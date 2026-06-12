"""Nobody 聊天接口"""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json, sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api.auth import get_current_user
import brain

router = APIRouter(prefix="/api/chat", tags=["chat"])

class AskReq(BaseModel):
    question: str
    stream: bool = True

@router.get("/welcome")
def welcome(user: str = Depends(get_current_user)):
    """获取欢迎消息 + 用户记忆"""
    return {"code": 0, "data": brain.Memory.welcome(user)}

@router.post("/profile/parse")
def parse_profile(req: AskReq, user: str = Depends(get_current_user)):
    """尝试解析用户身份"""
    result = brain.Memory.try_parse(user, req.question)
    return {"code": 0, "data": result}

@router.post("/ask")
def chat_ask(req: AskReq, user: str = Depends(get_current_user)):
    # 记录到学习记忆
    brain.Memory.record(user, req.question)

    # 检查是否新用户需要解析身份
    profile_parsed = brain.Memory.try_parse(user, req.question)

    if not req.stream:
        result = brain.ask(req.question)
        result["profile_parsed"] = profile_parsed
        return {"code": 0, "data": result}

    def generate():
        if profile_parsed:
            yield f"data: {json.dumps({'type':'profile_parsed','data':profile_parsed}, ensure_ascii=False)}\n\n"
        for event in brain.ask_stream(req.question):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
