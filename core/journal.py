"""
统一事件日志 — Memory / Experience / Timeline 的唯一写入入口

设计原则：
  - 所有事件走 Journal.add() 写入 events 表
  - Memory / Experience / Timeline 是不同的查询视图，不是不同的表
  - 写入简单，查询灵活
"""

import json
import os
from datetime import datetime
from uuid import uuid4
from typing import Optional
from store.database import Database

# 数据库路径：与现有 memory_core.db 共存，后续统一迁移
DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "nobody.db"
)

_db: Optional[Database] = None


def _get_db() -> Database:
    global _db
    if _db is None:
        _db = Database(DB_PATH)
        _db.initialize()
    return _db


class Journal:
    """统一事件日志"""

    # ── 写入 ──

    @staticmethod
    def add(
        type: str,
        summary: str,
        detail: str = "",
        tags: list = None,
        project_id: str = "",
        importance: int = 0,
        confirmed: bool = True,
    ) -> str:
        """
        唯一写入入口。

        type: 'memory' | 'learning' | 'research' | 'achievement' | 'note' | 'decision'
        """
        event_id = f"evt_{uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        with _get_db().connect() as conn:
            conn.execute(
                """INSERT INTO events (id, type, summary, detail, tags,
                   project_id, importance, created_at, confirmed)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    event_id,
                    type,
                    summary,
                    detail,
                    json.dumps(tags or [], ensure_ascii=False),
                    project_id,
                    importance,
                    now,
                    int(confirmed),
                ),
            )
        return event_id

    # ── 便捷写入 ──

    @staticmethod
    def learn(topic: str, detail: str = "", tags: list = None):
        """记录学习事件"""
        return Journal.add("learning", topic, detail, tags or [])

    @staticmethod
    def research(topic: str, detail: str = "", tags: list = None):
        """记录研究事件"""
        return Journal.add("research", topic, detail, tags or [])

    @staticmethod
    def achieve(title: str, detail: str = "", tags: list = None):
        """记录成就事件"""
        return Journal.add("achievement", title, detail, tags or [], importance=5)

    @staticmethod
    def remember(content: str, tags: list = None):
        """保存长期记忆（需确认）"""
        return Journal.add("memory", content, "", tags or [], confirmed=True)

    @staticmethod
    def note(content: str, tags: list = None):
        """保存笔记"""
        return Journal.add("note", content, "", tags or [])

    @staticmethod
    def decide(content: str, project_id: str = ""):
        """记录决策"""
        return Journal.add("decision", content, "", project_id=project_id, importance=3)

    # ── 查询 ──

    @staticmethod
    def query(
        types: list = None,
        tags: list = None,
        project_id: str = None,
        since: str = None,
        confirmed: bool = None,
        limit: int = 20,
    ) -> list[dict]:
        """统一查询入口。默认排除软删除条目 (confirmed != -1)。"""
        conditions = ["confirmed != -1"]  # 始终排除软删除
        params = []

        if types:
            placeholders = ",".join("?" * len(types))
            conditions.append(f"type IN ({placeholders})")
            params.extend(types)
        if project_id is not None:
            conditions.append("project_id = ?")
            params.append(project_id)
        if since:
            conditions.append("created_at >= ?")
            params.append(since)
        if confirmed is not None:
            conditions.append("confirmed = ?")
            params.append(int(confirmed))

        where = " AND ".join(conditions)
        sql = f"SELECT * FROM events WHERE {where} ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with _get_db().connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_dict(r) for r in rows]

    # ── 视图 ──

    @staticmethod
    def memories(limit: int = 20) -> list[dict]:
        """长期记忆视图：已确认的 memory + note"""
        return Journal.query(
            types=["memory", "note"], confirmed=True, limit=limit
        )

    @staticmethod
    def experiences(days: int = 30, limit: int = 20) -> list[dict]:
        """经验视图：学习 + 研究 + 成就"""
        from datetime import timedelta
        since = (datetime.now() - timedelta(days=days)).isoformat()
        return Journal.query(
            types=["learning", "research", "achievement"],
            since=since,
            limit=limit,
        )

    @staticmethod
    def timeline(days: int = 30, limit: int = 30) -> list[dict]:
        """时间线视图：按日期聚合所有事件"""
        from datetime import timedelta
        since = (datetime.now() - timedelta(days=days)).isoformat()
        events = Journal.query(since=since, limit=limit)

        # 按日期分组
        grouped = {}
        for evt in events:
            date_key = evt["created_at"][:10]
            if date_key not in grouped:
                grouped[date_key] = []
            grouped[date_key].append(evt)

        return [
            {"date": d, "events": evts}
            for d, evts in sorted(grouped.items(), reverse=True)
        ]

    @staticmethod
    def recent(days: int = 7, limit: int = 10) -> list[dict]:
        """最近事件摘要"""
        from datetime import timedelta
        since = (datetime.now() - timedelta(days=days)).isoformat()
        return Journal.query(since=since, limit=limit)

    @staticmethod
    def count() -> int:
        """事件总数"""
        with _get_db().connect() as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM events").fetchone()
        return row["cnt"] if row else 0


def _row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "type": row["type"],
        "summary": row["summary"],
        "detail": row["detail"],
        "tags": json.loads(row["tags"]) if row["tags"] else [],
        "project_id": row["project_id"],
        "importance": row["importance"],
        "created_at": row["created_at"],
        "confirmed": bool(row["confirmed"]),
    }
