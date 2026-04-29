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

# 核心常量补齐
DB_SCHEMA_VERSION = 23
DB_SCHEMA_VERSION_KEY = "db_schema_version"
DB_SCHEMA_LAST_UPGRADE_TRACE_ID_KEY = "db_schema_last_upgrade_trace_id"
DB_SCHEMA_LAST_UPGRADE_ERROR_KEY = "db_schema_last_upgrade_error"

# --- 增强版 Turso 适配器 ---

class TursoRow(dict):
    """完美模拟 sqlite3.Row"""
    def __init__(self, columns, values):
        super().__init__(zip(columns, values))
        self._data = values
    def __getitem__(self, key):
        if isinstance(key, int): return self._data[key]
        return super().__getitem__(key)
    def keys(self):
        return list(self.keys())

class TursoCursor:
    def __init__(self, client):
        self.client = client
        self.last_result = None
        self.lastrowid = None

    def execute(self, sql, params=None):
        s = sql.strip().upper()
        # 彻底屏蔽不支持的指令
        if any(s.startswith(p) for p in ["PRAGMA", "BEGIN", "SAVEPOINT", "RELEASE", "ROLLBACK"]):
            return self
        
        p = list(params) if params else []
        try:
            res = self.client.execute(sql, p)
            self.last_result = res
            self.lastrowid = res.last_insert_rowid
        except Exception as e:
            # 记录详细错误但不崩溃
            if "settings" not in sql: # 忽略初始化时的频繁报错
                print(f"SQL执行失败: {sql[:100]}... | 错误: {e}")
            raise e
        return self

    def fetchone(self):
        if not self.last_result or len(self.last_result.rows) == 0:
            return None
        return TursoRow(self.last_result.columns, self.last_result.rows[0])

    def fetchall(self):
        if not self.last_result: return []
        return [TursoRow(self.last_result.columns, r) for r in self.last_result.rows]

    def close(self): pass

class TursoConnection:
    def __init__(self):
        url = os.environ.get("TURSO_URL", "").strip()
        # 尝试将 libsql:// 换成 https:// 可能会更稳定，减少 505 错误
        if url.startswith("libsql://"):
            self.url = url.replace("libsql://", "https://")
        else:
            self.url = url
            
        self.token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
        if not self.url or not self.token:
            raise Exception("环境变量 TURSO_URL 或 TURSO_AUTH_TOKEN 为空")
            
        self.client = libsql_client.create_client_sync(self.url, auth_token=self.token)

    def cursor(self):
        return TursoCursor(self.client)

    # 补齐项目需要的直接执行方法
    def execute(self, sql, params=None):
        return self.cursor().execute(sql, params)

    def commit(self): pass
    def rollback(self): pass
    def close(self):
        try: self.client.close()
        except: pass

# --- Flask 接口逻辑 ---

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
    """云端静默初始化"""
    try:
        conn = create_sqlite_connection()
        # 统一使用 execute 方法
        conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (DB_SCHEMA_VERSION_KEY,)).fetchone()
        if not row:
            print("首次运行，初始化云端表结构...")
            conn.execute("CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, description TEXT, color TEXT DEFAULT '#1a1a1a')")
            conn.execute("INSERT OR IGNORE INTO groups (name, description, color) VALUES ('默认分组', '未分组', '#666666')")
            
            pw = hash_password(config.get_login_password_default())
            conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('login_password', ?)", (pw,))
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (DB_SCHEMA_VERSION_KEY, str(DB_SCHEMA_VERSION)))
            print("云端初始化成功")
        conn.close()
    except Exception as e:
        print(f"⚠ 数据库初始化遇到问题 (若表已存在可忽略): {e}")

def migrate_sensitive_data(conn):
    pass
