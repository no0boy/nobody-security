"""
飞书 Webhook — Nobody 直接接入飞书群机器人
配置：飞书开放平台 → 事件订阅 → 指向 https://你的HF/api/webhook/feishu
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import json, os

router = APIRouter(prefix="/api/webhook", tags=["飞书"])


@router.post("/feishu")
async def feishu_callback(request: Request):
    """接收飞书消息 → Nobody 处理 → 回复"""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"msg": "invalid"}, status_code=400)

    # 飞书 URL 验证（首次配置时）
    if body.get("type") == "url_verification":
        return JSONResponse({"challenge": body.get("challenge", "")})

    # 打印收到的请求（调试用）
    import sys
    print(f"[飞书] 收到请求: {json.dumps(body, ensure_ascii=False)[:300]}", flush=True)

    # 提取消息 — 兼容多种格式
    text = ""
    event = body.get("event", {}) or body.get("header", {})
    msg = event.get("message", {}) or event.get("event", {}).get("message", {})

    content = msg.get("content", "{}")
    try:
        text = json.loads(content).get("text", "")
    except Exception:
        text = content if isinstance(content, str) and len(content) < 500 else ""
    if not text:
        text = msg.get("text", "")

    print(f"[飞书] 提取文本: {text[:100]}", flush=True)

    if not text:
        return JSONResponse({"msg": "ok"})

    # 调 Nobody 大脑
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import brain
        result = brain.ask(text)
        answer = result.get("answer", "处理失败。")
    except Exception as e:
        answer = f"Nobody 处理失败：{str(e)[:100]}"

    # 飞书回复（通过消息 API）
    send_to = body.get("event", {}).get("sender", {}).get("sender_id", {}).get("open_id", "")
    chat_id = body.get("event", {}).get("message", {}).get("chat_id", "")

    if send_to or chat_id:
        _reply_feishu(send_to or chat_id, answer, chat_id)

    return JSONResponse({"msg": "ok"})


def _reply_feishu(target_id: str, text: str, chat_id: str = ""):
    """调用飞书发送消息 API"""
    import urllib.request

    feishu_app_id = os.getenv("FEISHU_APP_ID", "")
    feishu_app_secret = os.getenv("FEISHU_APP_SECRET", "")

    if not feishu_app_id:
        print("[飞书] 未配置 FEISHU_APP_ID，跳过回复")
        return

    # 获取 tenant_access_token
    try:
        token_data = json.dumps({"app_id": feishu_app_id, "app_secret": feishu_app_secret}).encode()
        req = urllib.request.Request("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                                     data=token_data, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=5)
        token = json.loads(resp.read().decode()).get("tenant_access_token", "")
    except Exception:
        return

    # 发送消息
    msg_body = json.dumps({
        "receive_id": target_id,
        "msg_type": "text",
        "content": json.dumps({"text": f"💀 Nobody：{text}"})
    }).encode()

    endpoint = "open_id" if chat_id else "chat_id"
    url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={endpoint}"
    req = urllib.request.Request(url, data=msg_body,
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {token}"})
    try:
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


@router.post("/send")
async def send_to_feishu(request: Request):
    """从 Web 端主动推送消息到飞书用户"""
    body = await request.json()
    open_id = body.get("open_id", os.getenv("FEISHU_DEFAULT_USER", ""))
    text = body.get("text", "")
    if not open_id or not text:
        return JSONResponse({"msg": "缺少 open_id 或 text"}, status_code=400)

    _reply_feishu(open_id, f"{text}")
    return {"msg": "ok", "sent_to": open_id}


@router.get("/health")
def webhook_health():
    return {"status": "ok", "channel": "feishu"}
