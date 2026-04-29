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

# 常量定义
DB_SCHEMA_VERSION = 23
DB_SCHEMA_VERSION_KEY = "db_schema_version"
DB_SCHEMA_LAST_UPGRADE_TRACE_ID_KEY = "db_schema_last_upgrade_trace_id"
DB_SCHEMA_LAST_UPGRADE_ERROR_KEY = "db_schema_last_upgrade_error"

# --- 完美模拟 sqlite3.Row 的类 ---
class TursoRow(dict):
    def __init__(self, columns, values):
        # 同时支持 row['key'] 和 row[index]
        super().__init__(zip(columns, values))
        self.data = values
    def __getitem__(self, key):
        if isinstance(key, int):
            return self.data[key]
        return super().__getitem__(key)

class TursoCursor:
    def __init__(self, client):
        self.client = client
        self.last_result = None
        self.lastrowid = None

    def execute(self, sql, params=None):
        s = sql.strip().upper()
        # 屏蔽 Turso 不支持的 SQLite 物理指令
        if any(s.startswith(p) for p in ["PRAGMA", "BEGIN", "SAVEPOINT", "RELEASE", "ROLLBACK"]):
            return self
        
        # 适配参数格式
        p = list(params) if params else []
        try:
            res = self.client.execute(sql, p)
            self.last_result = res
            self.lastrowid = res.last_insert_rowid
        except Exception as e:
            print(f"SQL执行失败: {sql} | 错误: {e}")
            raise e
        return self

    def fetchone(self):
        if not self.last_result or len(self.last_result.rows) == 0:
            return None
        return TursoRow(self.last_result.columns, self.last_result.rows[0])

    def fetchall(self):
        if not self.last_result:
            return []
        return [TursoRow(self.last_result.columns, r) for r in self.last_result.rows]

class TursoConnection:
    def __init__(self):
        url = os.environ.get("TURSO_URL", "").strip()
        # 强制修正协议头，防止 505 错误
        if url.startswith("https://"):
            url = url.replace("https://", "libsql://")
        elif url.startswith("wss://"):
            url = url.replace("wss://", "libsql://")
            
        token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
        if not url or not token:
            raise Exception("DATABASE_CONFIG_ERR: Missing TURSO_URL or TURSO_AUTH_TOKEN")
            
        # 使用同步客户端
        self.client = libsql_client.create_client_sync(url, auth_token=token)

    def cursor(self):
        return TursoCursor(self.client)

    def commit(self): pass
    def rollback(self): pass
    def close(self):
        self.client.close()

# --- Flask 接口 ---
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
    """静默初始化逻辑"""
    try:
        conn = create_sqlite_connection()
        cursor = conn.cursor()
        
        # 创建设置表
        cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        
        # 检查是否已初始化
        row = cursor.execute("SELECT value FROM settings WHERE key = ?", (DB_SCHEMA_VERSION_KEY,)).fetchone()
        if not row:
            print("首次运行，执行云端初始化...")
            # 执行最基础的建表，其余的由原有 Repository 逻辑自动补齐
            cursor.execute("CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, description TEXT, color TEXT DEFAULT '#1a1a1a')")
            cursor.execute("INSERT OR IGNORE INTO groups (name, description, color) VALUES ('默认分组', '未分组', '#666666')")
            
            hashed_pw = hash_password(config.get_login_password_default())
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('login_password', ?)", (hashed_pw,))
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (DB_SCHEMA_VERSION_KEY, str(DB_SCHEMA_VERSION)))
            print("云端初始化成功")
        conn.close()
    except Exception as e:
        print(f"⚠ 数据库初始化跳过或失败: {e}")

def migrate_sensitive_data(conn):
    pass
