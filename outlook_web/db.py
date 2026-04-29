from __future__ import annotations
import os
import time
from typing import Optional
from flask import g
import libsql_client
from outlook_web import config
from outlook_web.errors import generate_trace_id, sanitize_error_details
from outlook_web.security.crypto import (
    encrypt_data,
    hash_password,
    is_encrypted,
    is_password_hashed,
)

# 核心常量
DB_SCHEMA_VERSION = 23
DB_SCHEMA_VERSION_KEY = "db_schema_version"
DB_SCHEMA_LAST_UPGRADE_TRACE_ID_KEY = "db_schema_last_upgrade_trace_id"
DB_SCHEMA_LAST_UPGRADE_ERROR_KEY = "db_schema_last_upgrade_error"

class TursoRow:
    """超强仿真 sqlite3.Row"""
    def __init__(self, columns: list[str], values: list):
        self._columns = columns
        self._values = values
        self._dict = dict(zip(columns, values))

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._dict[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def keys(self):
        return self._columns

    def get(self, key, default=None):
        return self._dict.get(key, default)

    def __repr__(self):
        return str(self._dict)

class TursoCursor:
    def __init__(self, client):
        self.client = client
        self.last_result = None
        self.lastrowid = None
        self.rowcount = 0
        self._columns = []
        self._pos = 0

    def execute(self, sql, params=None):
        s = sql.strip().upper()
        # 屏蔽物理文件/事务指令
        if any(s.startswith(p) for p in ["PRAGMA", "BEGIN", "SAVEPOINT", "RELEASE", "ROLLBACK"]):
            return self
        
        p = list(params) if params else []
        try:
            res = self.client.execute(sql, p)
            self.last_result = res
            self.lastrowid = getattr(res, "last_insert_rowid", None)
            self.rowcount = getattr(res, "rows_affected", 0)
            self._columns = list(getattr(res, "columns", []))
            self._pos = 0
        except Exception as e:
            if "settings" not in sql:
                print(f"[Turso Error] SQL: {sql[:100]} | Error: {e}")
            raise e
        return self

    def fetchone(self):
        if not self.last_result or self._pos >= len(self.last_result.rows):
            return None
        row = self.last_result.rows[self._pos]
        self._pos += 1
        return TursoRow(self._columns, row)

    def fetchall(self):
        if not self.last_result:
            return []
        rows = []
        while True:
            row = self.fetchone()
            if row is None: break
            rows.append(row)
        return rows

    def __iter__(self):
        """支持 for row in cursor 语法"""
        while True:
            row = self.fetchone()
            if row is None: break
            yield row

    def close(self):
        pass

class TursoConnection:
    def __init__(self):
        raw_url = os.environ.get("TURSO_URL", "").strip()
        # 强制 HTTPS 解决 Render 的 505 WebSocket 兼容性问题
        self.url = raw_url.replace("libsql://", "https://").replace("wss://", "https://")
        if not self.url.startswith("https://"):
            self.url = f"https://{self.url}"
            
        self.token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
        self.client = libsql_client.create_client_sync(self.url, auth_token=self.token)

    def cursor(self):
        return TursoCursor(self.client)

    def execute(self, sql, params=None):
        return self.cursor().execute(sql, params)

    def __enter__(self): return self
    def __exit__(self, exc_type, exc_val, exc_tb): pass
    
    def commit(self): pass
    def rollback(self): pass
    def close(self):
        try: self.client.close()
        except: pass

# --- Flask 接口逻辑 ---

def create_sqlite_connection(_path=None):
    return TursoConnection()

def get_db():
    if '_database' not in g:
        g._database = create_sqlite_connection()
    return g._database

def close_db(e=None):
    db = g.pop('_database', None)
    if db is not None:
        db.close()

def register_db(app):
    app.teardown_appcontext(close_db)

def init_db(database_path: Optional[str] = None):
    """静默初始化逻辑"""
    try:
        print("--- 执行云端数据库自检 ---")
        with create_sqlite_connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            res = db.execute("SELECT value FROM settings WHERE key = ?", (DB_SCHEMA_VERSION_KEY,))
            row = res.fetchone()
            if not row:
                print("首次运行，初始化云端表结构...")
                db.execute("CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, description TEXT, color TEXT DEFAULT '#1a1a1a')")
                db.execute("INSERT OR IGNORE INTO groups (name, description, color) VALUES ('默认分组', '未分组的邮箱', '#666666')")
                pw = hash_password(config.get_login_password_default())
                db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('login_password', ?)", (pw,))
                db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (DB_SCHEMA_VERSION_KEY, str(DB_SCHEMA_VERSION)))
            print("✅ 数据库状态检查完毕")
    except Exception as e:
        print(f"⚠ 初始化跳过: {e}")

def migrate_sensitive_data(conn):
    pass
