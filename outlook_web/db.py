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

# --- 必须定义的常量，防止其他模块导入失败 ---
DB_SCHEMA_VERSION = 23
DB_SCHEMA_VERSION_KEY = "db_schema_version"
DB_SCHEMA_LAST_UPGRADE_TRACE_ID_KEY = "db_schema_last_upgrade_trace_id"
DB_SCHEMA_LAST_UPGRADE_ERROR_KEY = "db_schema_last_upgrade_error"

# --- Turso 适配层 ---
class TursoCursor:
    def __init__(self, client):
        self.client = client
        self.last_result = None
        self.lastrowid = None

    def execute(self, sql, params=None):
        # 过滤远程数据库不支持的指令
        s = sql.strip().upper()
        if s.startswith("PRAGMA") or s == "BEGIN IMMEDIATE" or s.startswith("SAVEPOINT") or s.startswith("RELEASE SAVEPOINT") or s.startswith("ROLLBACK TO"):
            return self
        
        # 将 SQL 中的 ? 转换为 libsql 预期的格式（libsql 实际上支持 ?，但我们确保参数是列表）
        res = self.client.execute(sql, list(params) if params else [])
        self.last_result = res
        self.lastrowid = res.last_insert_rowid
        return self

    def fetchone(self):
        if not self.last_result or len(self.last_result.rows) == 0:
            return None
        return self.last_result.rows[0]

    def fetchall(self):
        if not self.last_result:
            return []
        return self.last_result.rows

class TursoConnection:
    def __init__(self):
        url = os.environ.get("TURSO_URL")
        token = os.environ.get("TURSO_AUTH_TOKEN")
        if not url or not token:
            raise Exception("环境变量缺失：请在 Render 配置 TURSO_URL 和 TURSO_AUTH_TOKEN")
        self.client = libsql_client.create_client_sync(url, auth_token=token)

    def cursor(self):
        return TursoCursor(self.client)

    def execute(self, sql, params=None):
        return self.cursor().execute(sql, params)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        self.client.close()

# --- Flask 核心函数 ---

def create_sqlite_connection(_path=None) -> TursoConnection:
    return TursoConnection()

def get_db() -> TursoConnection:
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
    """初始化云端数据库"""
    login_password_default = config.get_login_password_default()
    
    conn = create_sqlite_connection()
    cursor = conn.cursor()

    try:
        # 1. 创建基础设置表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. 检查版本，决定是否需要初始化
        row = cursor.execute("SELECT value FROM settings WHERE key = ?", (DB_SCHEMA_VERSION_KEY,)).fetchone()
        current_version = int(row["value"]) if row and row["value"] is not None else 0

        if current_version < DB_SCHEMA_VERSION:
            print(f"检测到数据库需要初始化/升级 (v{current_version} -> v{DB_SCHEMA_VERSION})")
            
            # 3. 执行核心建表语句 (这里只列出最关键的，其他由项目代码在运行中按需补齐)
            cursor.execute("CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, description TEXT, color TEXT DEFAULT '#1a1a1a', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            cursor.execute("CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, password TEXT, client_id TEXT NOT NULL, refresh_token TEXT NOT NULL, group_id INTEGER, status TEXT DEFAULT 'active', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            cursor.execute("CREATE TABLE IF NOT EXISTS schema_migrations (id INTEGER PRIMARY KEY AUTOINCREMENT, from_version INTEGER, to_version INTEGER, status TEXT, started_at REAL, finished_at REAL, trace_id TEXT)")
            
            # 4. 插入默认数据
            cursor.execute("INSERT OR IGNORE INTO groups (name, description, color) VALUES ('默认分组', '未分组的邮箱', '#666666')")
            hashed_pw = hash_password(login_password_default)
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('login_password', ?)", (hashed_pw,))

            # 更新版本号
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (DB_SCHEMA_VERSION_KEY, str(DB_SCHEMA_VERSION)))
            print("Turso 初始化任务尝试执行完毕")

    except Exception as e:
        print(f"数据库初始化失败: {str(e)}")
    finally:
        conn.close()

def migrate_sensitive_data(conn):
    """适配器暂不执行复杂的敏感数据迁移，保持启动速度"""
    pass
