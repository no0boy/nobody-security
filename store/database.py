"""
统一 SQLite 连接管理

用法:
    db = Database("data/memory.db")
    db.initialize()  # 启动时调用一次

    with db.connect() as conn:
        conn.execute("SELECT ...")
"""

import sqlite3
import os
from contextlib import contextmanager
from threading import Lock


SCHEMA = """
-- Nobody v3.0 数据模型: 统一事件流 + 身份 + 会话日志

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK(type IN (
        'memory','learning','research','achievement','note','decision'
    )),
    summary TEXT NOT NULL,
    detail TEXT DEFAULT '',
    tags JSON DEFAULT '[]',
    project_id TEXT DEFAULT '',
    importance INT DEFAULT 0,
    created_at TEXT NOT NULL,
    confirmed INT DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_events_type_time
    ON events(type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_project
    ON events(project_id, created_at DESC);

CREATE TABLE IF NOT EXISTS profile (
    key TEXT PRIMARY KEY,
    value JSON NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS preference (
    key TEXT PRIMARY KEY,
    value JSON NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('master','nobody','system')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_convlog_session
    ON conversation_log(session_id, created_at);
"""


class Database:
    """SQLite 数据库管理器 —— 请求级连接复用"""

    def __init__(self, path: str):
        self._path = path
        self._lock = Lock()
        self._initialized = False

    @property
    def path(self) -> str:
        return self._path

    def initialize(self):
        """启动时调用一次，创建所有表和索引"""
        if self._initialized:
            return
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)
        self._initialized = True
        print(f"[Database] 已初始化: {self._path}")

    @contextmanager
    def connect(self):
        """获取一个连接（请求级生命周期）"""
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def transaction(self):
        """需要多步原子写入时使用"""
        with self.connect() as conn:
            try:
                yield conn
            except Exception:
                conn.rollback()
                raise
