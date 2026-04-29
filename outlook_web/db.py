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
    """高度仿真的 Row 对象，支持各种访问方式，防止 KeyError"""
    def __init__(self, columns: list[str], values: list):
        self._columns = columns
        self._values = values
        # 预先构建字典
        super().__init__(zip(columns, values))

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key] if key < len(self._values) else None
        # 如果 key 不存在，返回 None 而不是抛出 KeyError，防止项目代码因版本差异崩溃
        return super().get(key)

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def keys(self):
        return self._columns

    def get(self, key, default=None):
        return super().get(key, default)

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
        # 彻底屏蔽不支持的 SQLite 特有物理/事务指令
        if any(s.startswith(p) for p in ["PRAGMA", "BEGIN", "SAVEPOINT", "RELEASE", "ROLLBACK"]):
            return self
        
        p = list(params) if params else []
        try:
            res = self.client.execute(sql, p)
            self.last_result = res
            # 安全获取属性，libsql-client 的 ResultSet 结构处理
            self.lastrowid = getattr(res, "last_insert_rowid", None)
            self.rowcount = getattr(res, "rows_affected", 0)
            self._columns = list(getattr(res, "columns", []))
            self._pos = 0
        except Exception as e:
            # 仅记录关键业务 SQL 错误
            if "settings" not in sql and "UPDATE" not in sql:
                print(f"[Turso SQL Error] {e} | SQL: {sql[:100]}")
            raise e
        return self

    def fetchone(self):
        if not self.last_result or not hasattr(self.last_result, "rows"):
            return None
        if self._pos >= len(self.last_result.rows):
            return None
        row = self.last_result.rows[self._pos]
        self._pos += 1
        return TursoRow(self._columns, row)

    def fetchall(self):
        if not self.last_result or not hasattr(self.last_result, "rows"):
            return []
        results = []
        while True:
            row = self.fetchone()
            if row is None: break
            results.append(row)
        return results

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
        # 强制使用 HTTPS 模式，这是 Render 环境下最稳定的协议，解决 505 错误
        self.url = raw_url.replace("libsql://", "https://").replace("wss://", "https://")
        if not self.url.startswith("https://"):
            self.url = f"https://{self.url}"
            
        self.token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
        if not self.url or not self.token:
            raise Exception("TURSO_CONFIG_MISSING: Check TURSO_URL and TURSO_AUTH_TOKEN in Render")
            
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

# --- Flask 接口函数 ---

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
    """云端自检与静默初始化"""
    try:
        with create_sqlite_connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            res = db.execute("SELECT value FROM settings WHERE key = ?", (DB_SCHEMA_VERSION_KEY,))
            row = res.fetchone()
            if not row:
                print("Detected new Turso DB. Initializing schema...")
                db.execute("CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, description TEXT, color TEXT DEFAULT '#1a1a1a')")
                db.execute("INSERT OR IGNORE INTO groups (name, description, color) VALUES ('默认分组', '未分组', '#666666')")
                pw = hash_password(config.get_login_password_default())
                db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('login_password', ?)", (pw,))
                db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (DB_SCHEMA_VERSION_KEY, str(DB_SCHEMA_VERSION)))
                print("✅ Turso Schema Init Success")
            else:
                print(f"✅ Turso DB Connected. Version: {row['value']}")
    except Exception as e:
        print(f"⚠ Init Check Notice: {e}")

def migrate_sensitive_data(conn):
    pass
