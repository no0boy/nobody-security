"""人格系统 — Nobody 的身份和说话风格"""
import json, os

PERSONA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "persona.json")

_persona = None

def load():
    global _persona
    with open(PERSONA_FILE, "r", encoding="utf-8") as f:
        _persona = json.load(f)
    return _persona

def get(key, default=None):
    if _persona is None: load()
    return _persona.get(key, default) if _persona else default

def name():
    return get("name", "Nobody")

def identity():
    return get("identity", "")

def voice(key, default=""):
    v = get("voice", {})
    return v.get(key, default) if v else default

def tone(severity):
    tones = get("tones", {})
    return tones.get(severity, get("style", "直接"))

def greeting(user_type="guest"):
    v = get("voice", {})
    if not v: return "Nobody 在线。"
    if user_type == "new": return v.get("first_time", "Nobody 在线。")
    if user_type == "returning": return v.get("returning", "回来了。")
    return v.get("guest", "Nobody 在线。")

# 启动时加载
load()
