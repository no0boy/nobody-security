"""
Master 身份 + 偏好管理

Profile  — 永久身份（姓名/目标/职业/身份），很少修改
Preference — 可更新偏好（回答风格/代码风格/学习方式/UI）
"""

import json
from datetime import datetime
from typing import Optional
from store.database import Database
from core.journal import _get_db as _get_journal_db


# Profile 复用 journal 的数据库（同一文件，不同表）
def _db() -> Database:
    return _get_journal_db()


class Profile:
    """Master 永久身份"""

    @staticmethod
    def get(key: str, default=None):
        with _db().connect() as conn:
            row = conn.execute(
                "SELECT value FROM profile WHERE key=?", (key,)
            ).fetchone()
        return json.loads(row["value"]) if row else default

    @staticmethod
    def set(key: str, value):
        with _db().connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO profile VALUES (?,?,?)",
                (key, json.dumps(value, ensure_ascii=False),
                 datetime.now().isoformat()),
            )

    @staticmethod
    def all() -> dict:
        with _db().connect() as conn:
            rows = conn.execute("SELECT key, value FROM profile").fetchall()
        return {r["key"]: json.loads(r["value"]) for r in rows}

    @staticmethod
    def identity_summary() -> str:
        """
        生成身份摘要，用于上下文注入。
        控制在 300 字符以内。
        """
        p = Profile.all()
        if not p:
            return ""

        parts = []
        if p.get("name"):
            parts.append(p["name"])
        if p.get("role"):
            parts.append(f"角色：{p['role']}")
        if p.get("level"):
            parts.append(f"水平：{p['level']}")
        if p.get("goals"):
            goals = p["goals"]
            if isinstance(goals, list):
                parts.append(f"目标：{', '.join(goals[:3])}")
        if p.get("identity"):
            parts.append(p["identity"])

        summary = "Master 信息：" + " | ".join(parts)
        return summary[:300]

    @staticmethod
    def initialize(name: str = "", role: str = "", goals: list = None):
        """首次设置 Master 身份"""
        if name:
            Profile.set("name", name)
        if role:
            Profile.set("role", role)
        if goals:
            Profile.set("goals", goals)
        Profile.set("joined_at", datetime.now().isoformat())


class Preference:
    """Master 偏好（可更新）"""

    DEFAULTS = {
        "language": "中文",
        "response_style": "先原理后操作",
        "depth": "详细",
        "code_style": "Python, 简洁",
        "learning_style": "项目驱动",
        "tone": "直接",
    }

    @staticmethod
    def get(key: str, default=None):
        val = _pref_get(key)
        if val is None:
            return Preference.DEFAULTS.get(key, default)
        return val

    @staticmethod
    def set(key: str, value):
        with _db().connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO preference VALUES (?,?,?)",
                (key, json.dumps(value, ensure_ascii=False),
                 datetime.now().isoformat()),
            )

    @staticmethod
    def all() -> dict:
        with _db().connect() as conn:
            rows = conn.execute("SELECT key, value FROM preference").fetchall()
        stored = {r["key"]: json.loads(r["value"]) for r in rows}
        # 合并默认值
        merged = {**Preference.DEFAULTS, **stored}
        return merged

    @staticmethod
    def summary() -> str:
        """
        生成偏好摘要，用于上下文注入。
        控制在 200 字符以内。
        """
        prefs = Preference.all()
        parts = []
        if prefs.get("language"):
            parts.append(f"语言:{prefs['language']}")
        if prefs.get("response_style"):
            parts.append(f"风格:{prefs['response_style']}")
        if prefs.get("depth"):
            parts.append(f"深度:{prefs['depth']}")
        if prefs.get("code_style"):
            parts.append(f"代码:{prefs['code_style']}")
        if prefs.get("tone"):
            parts.append(f"语气:{prefs['tone']}")
        return "偏好：" + " | ".join(parts) if parts else ""


def _pref_get(key: str):
    with _db().connect() as conn:
        row = conn.execute(
            "SELECT value FROM preference WHERE key=?", (key,)
        ).fetchone()
    return json.loads(row["value"]) if row else None
