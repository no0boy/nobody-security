"""
Nobody 聊天接口

权限规则：
  游客(guest)  → 只能搜索公共知识，不存记忆，不可修改任何数据
  注册用户     → 搜索公共知识 + 自己的私人学习记忆（互不可见）
  nobody(主人) → 唯一可修改公共知识层的账号
"""
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
    # 游客不记录记忆
    if user != "guest":
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


@router.get("/planner")
def planner(user: str = Depends(get_current_user)):
    """主动规划建议"""
    if user == "guest":
        return {"code": 0, "data": {"suggestions": ["注册账号后，Nobody 可以帮你规划学习路线。"]}}
    result = brain.planner_check(user)
    return {"code": 0, "data": result}


@router.post("/multi-agent")
def multi_agent(req: AskReq, user: str = Depends(get_current_user)):
    """多Agent协作分析"""
    if user != "guest":
        brain.Memory.record(user, req.question)

    result = brain.multi_agent_think(req.question)

    if not req.stream:
        return {"code": 0, "data": result}

    def generate():
        if result.get("agents_used"):
            yield f"data: {json.dumps({'type': 'agents', 'agents': result['agents_used'], 'collaborative': True}, ensure_ascii=False)}\n\n"
        for event in brain.ask_stream(req.question):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
