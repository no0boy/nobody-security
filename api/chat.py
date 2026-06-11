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

@router.post("/ask")
def chat_ask(req: AskReq, user: str = Depends(get_current_user)):
    if not req.stream:
        result = brain.ask(req.question)
        return {"code": 0, "data": result}

    def generate():
        for event in brain.ask_stream(req.question):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
