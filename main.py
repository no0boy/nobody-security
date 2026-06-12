"""Nobody — FastAPI 入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import uvicorn, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from api.auth import router as auth_router
from api.chat import router as chat_router
from api.webhook import router as webhook_router
import brain

app = FastAPI(title="Nobody Security Partner", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(webhook_router)

FRONTEND = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(FRONTEND):
    app.mount("/app", StaticFiles(directory=FRONTEND, html=True), name="frontend")

@app.get("/")
def root():
    return RedirectResponse(url="/app/login.html")

@app.get("/health")
def health():
    return {"status": "ok", "name": "Nobody"}

@app.on_event("startup")
def startup():
    print("[Nobody] 启动中...")
    brain.init_knowledge()
    print("[Nobody] 就绪。")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
