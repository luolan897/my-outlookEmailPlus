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

class TursoRow(dict):
    """适配器：模拟 sqlite3.Row"""
    def __init__(self, cursor, values):
        self._columns = cursor._columns
        self._values = values
        super().__init__(zip(self._columns, values))
    def __getitem__(self, key):
        if isinstance(key, int): return self._values[key]
        return super().__getitem__(key)
    def keys(self): return self._columns

class TursoCursor:
    def __init__(self, client):
        self.client = client
        self.last_result = None
        self.lastrowid = None
        self._columns = []

    def execute(self, sql, params=None):
        s = sql.strip().upper()
        # 屏蔽物理文件指令
        if any(s.startswith(p) for p in ["PRAGMA", "BEGIN", "SAVEPOINT", "RELEASE", "ROLLBACK"]):
            return self
        
        p = list(params) if params else []
        try:
            res = self.client.execute(sql, p)
            self.last_result = res
            self.lastrowid = res.last_insert_rowid
            self._columns = res.columns
        except Exception as e:
            # 只有设置表以外的报错才打印，避免初始化干扰
            if "settings" not in sql:
                print(f"[Turso Error] SQL: {sql[:80]} | Error: {e}")
            raise e
        return self

    def fetchone(self):
        if not self.last_result or len(self.last_result.rows) == 0: return None
        return TursoRow(self, self.last_result.rows[0])

    def fetchall(self):
        if not self.last_result: return []
        return [TursoRow(self, r) for r in self.last_result.rows]

    def close(self): pass

class TursoConnection:
    def __init__(self):
        raw_url = os.environ.get("TURSO_URL", "").strip()
        # 【关键修复】强制将 libsql:// 转换为 https://
        # Render 经常拦截 wss (WebSocket)，而 https 是万能的
        self.url = raw_url.replace("libsql://", "https://").replace("wss://", "https://")
        if not self.url.startswith("https://"):
            self.url = f"https://{self.url}"
            
        self.token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
        
        if not self.url or not self.token:
            print("❌ 错误：环境变量 TURSO_URL 或 TURSO_AUTH_TOKEN 未设置！")
            raise Exception("DATABASE_CONFIG_MISSING")

        print(f"🚀 正在连接 Turso 数据库: {self.url}")
        try:
            self.client = libsql_client.create_client_sync(self.url, auth_token=self.token)
        except Exception as e:
            print(f"❌ 建立连接失败: {e}")
            raise e

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

# --- Flask 接口 ---

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
        print("--- 开始数据库自检 ---")
        db = create_sqlite_connection()
        # 创建设置表（最基础的表）
        db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        
        res = db.execute("SELECT value FROM settings WHERE key = ?", (DB_SCHEMA_VERSION_KEY,))
        row = res.fetchone()
        
        if not row:
            print("检测到新数据库，正在初始化表结构...")
            # 基础建表，其余的由 repositories 逻辑自动补齐
            db.execute("CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, description TEXT, color TEXT DEFAULT '#1a1a1a')")
            db.execute("INSERT OR IGNORE INTO groups (name, description, color) VALUES ('默认分组', '未分组', '#666666')")
            
            pw = hash_password(config.get_login_password_default())
            db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('login_password', ?)", (pw,))
            db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (DB_SCHEMA_VERSION_KEY, str(DB_SCHEMA_VERSION)))
            print("✅ 数据库初始化脚本执行成功")
        else:
            print(f"✅ 数据库连接正常，当前版本: {row['value']}")
        db.close()
    except Exception as e:
        print(f"⚠ 数据库初始化状态: {e}")

def migrate_sensitive_data(conn):
    pass
