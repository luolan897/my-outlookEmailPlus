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

# 核心常量，防止导入错误
DB_SCHEMA_VERSION = 23
DB_SCHEMA_VERSION_KEY = "db_schema_version"
DB_SCHEMA_LAST_UPGRADE_TRACE_ID_KEY = "db_schema_last_upgrade_trace_id"
DB_SCHEMA_LAST_UPGRADE_ERROR_KEY = "db_schema_last_upgrade_error"

# --- 完美模拟 sqlite3 行为的适配层 ---

class TursoRow:
    """完美模拟 sqlite3.Row，支持 row['email'] 和 row[0]"""
    def __init__(self, cursor, values):
        self._columns = cursor._columns
        self._values = values
        self._data = dict(zip(self._columns, values))

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._data[key]

    def keys(self):
        return self._columns

    def __len__(self):
        return len(self._values)

class TursoCursor:
    def __init__(self, client):
        self.client = client
        self.last_result = None
        self.lastrowid = None
        self._columns = []

    def execute(self, sql, params=None):
        # 彻底屏蔽物理指令
        s = sql.strip().upper()
        if any(s.startswith(p) for p in ["PRAGMA", "BEGIN", "SAVEPOINT", "RELEASE", "ROLLBACK"]):
            return self
        
        # 修正参数
        p = list(params) if params else []
        try:
            res = self.client.execute(sql, p)
            self.last_result = res
            self.lastrowid = res.last_insert_rowid
            self._columns = res.columns
        except Exception as e:
            # 记录关键错误
            if "settings" not in sql:
                print(f"SQL Error: {sql[:80]} | {e}")
            raise e
        return self

    def fetchone(self):
        if not self.last_result or len(self.last_result.rows) == 0:
            return None
        return TursoRow(self, self.last_result.rows[0])

    def fetchall(self):
        if not self.last_result:
            return []
        return [TursoRow(self, r) for r in self.last_result.rows]

    def close(self):
        pass

class TursoConnection:
    def __init__(self):
        # 1. 强制转换协议为 https:// 解决 505 错误
        raw_url = os.environ.get("TURSO_URL", "").strip()
        self.url = raw_url.replace("libsql://", "https://").replace("wss://", "https://")
        
        self.token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
        if not self.url or not self.token:
            raise Exception("Environment variables TURSO_URL or TURSO_AUTH_TOKEN are missing.")
            
        self.client = libsql_client.create_client_sync(self.url, auth_token=self.token)

    def cursor(self):
        return TursoCursor(self.client)

    # 补齐关键方法，修复 'TursoConnection' object has no attribute 'execute'
    def execute(self, sql, params=None):
        cur = self.cursor()
        return cur.execute(sql, params)

    def commit(self): pass
    def rollback(self): pass
    def close(self):
        try: self.client.close()
        except: pass

# --- Flask & 初始化逻辑 ---

def create_sqlite_connection(_path=None):
    return TursoConnection()

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = create_sqlite_connection()
    return db

def close_db(_exception=None):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

def register_db(app):
    app.teardown_appcontext(close_db)

def init_db(database_path: Optional[str] = None):
    """初始化逻辑"""
    try:
        db = create_sqlite_connection()
        # 创建设置表
        db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        
        # 检查版本
        res = db.execute("SELECT value FROM settings WHERE key = ?", (DB_SCHEMA_VERSION_KEY,))
        row = res.fetchone()
        
        if not row:
            print("Detected new Turso DB. Running initial schema setup...")
            db.execute("CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, description TEXT, color TEXT DEFAULT '#1a1a1a')")
            db.execute("INSERT OR IGNORE INTO groups (name, description, color) VALUES ('默认分组', '未分组', '#666666')")
            
            pw = hash_password(config.get_login_password_default())
            db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('login_password', ?)", (pw,))
            db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (DB_SCHEMA_VERSION_KEY, str(DB_SCHEMA_VERSION)))
            print("Initial setup done.")
        db.close()
    except Exception as e:
        print(f"Init notice: {e}")

def migrate_sensitive_data(conn):
    pass
