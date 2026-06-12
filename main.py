"""Nobody — FastAPI 入口 v3.0"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import uvicorn
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── 路由导入 ──
from api.chat import router as chat_router           # v2.x 兼容
from api.webhook import router as webhook_router
from api.conversation import router as conv_router   # v3.0 新
from api.journal import router as journal_router     # v3.0 新
from api.profile import router as profile_router     # v3.0 新

from core.rag import init_knowledge

app = FastAPI(title="Nobody Security Partner", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 注册路由 ──
app.include_router(chat_router)       # /api/chat/*
app.include_router(webhook_router)    # /api/webhook/*
app.include_router(conv_router)       # /api/conversation/*
app.include_router(journal_router)    # /api/journal/*
app.include_router(profile_router)    # /api/profile/*

# ── 前端静态文件 ──
FRONTEND = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(FRONTEND):
    app.mount("/app", StaticFiles(directory=FRONTEND, html=True), name="frontend")


@app.get("/")
def root():
    return RedirectResponse(url="/app/login.html")


@app.get("/health")
def health():
    from core.journal import Journal
    return {
        "status": "ok",
        "name": "Nobody",
        "version": "3.0.0",
        "events_total": Journal.count(),
    }


@app.on_event("startup")
def startup():
    print("[Nobody v3.0] 启动中...")

    # 初始化知识库
    init_knowledge()

    # 初始化新数据库
    from core.journal import _get_db
    _get_db().initialize()

    print("[Nobody v3.0] 就绪。")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
