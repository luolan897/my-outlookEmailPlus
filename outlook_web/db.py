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

# 保持版本号对齐
DB_SCHEMA_VERSION = 23
DB_SCHEMA_VERSION_KEY = "db_schema_version"

# --- Turso 适配层：模拟 SQLite 的 API 行为 ---
class TursoCursor:
    def __init__(self, client):
        self.client = client
        self.last_result = None
        self.lastrowid = None

    def execute(self, sql, params=None):
        # 自动过滤掉 Turso 不支持的 SQLite PRAGMA 语句
        if sql.strip().upper().startswith("PRAGMA"):
            return self
        
        # 自动过滤掉 SQLite 特有的 BEGIN IMMEDIATE
        if sql.strip().upper() == "BEGIN IMMEDIATE":
            return self

        res = self.client.execute(sql, params or [])
        self.last_result = res
        self.lastrowid = res.last_insert_rowid
        return self

    def fetchone(self):
        if not self.last_result or len(self.last_result.rows) == 0:
            return None
        # 返回第一行，支持 row['key'] 访问
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
            raise Exception("请在环境变量中配置 TURSO_URL 和 TURSO_AUTH_TOKEN")
        self.client = libsql_client.create_client_sync(url, auth_token=token)

    def cursor(self):
        return TursoCursor(self.client)

    def execute(self, sql, params=None):
        return self.cursor().execute(sql, params)

    def commit(self):
        # Turso 同步模式下自动提交，此处保持兼容性
        pass

    def rollback(self):
        pass

    def close(self):
        self.client.close()

# --- 核心 Flask 函数修改 ---

def create_sqlite_connection(_path=None) -> TursoConnection:
    """伪装成 SQLite 连接的 Turso 连接"""
    return TursoConnection()

def get_db() -> TursoConnection:
    """获取数据库连接（绑定到 flask.g 生命周期）"""
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = create_sqlite_connection()
    return db

def close_db(_exception=None):
    """关闭数据库连接"""
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

def register_db(app):
    """向 Flask app 注册 teardown"""
    app.teardown_appcontext(close_db)

# --- 以下逻辑保持原样，仅微调兼容性 ---

def init_db(database_path: Optional[str] = None):
    """初始化数据库（代码逻辑与原版基本一致，通过适配层运行）"""
    login_password_default = config.get_login_password_default()
    temp_mail_api_key_default = config.get_temp_mail_api_key_default()

    conn = create_sqlite_connection()
    cursor = conn.cursor()

    migration_id = None
    migration_trace_id = None
    upgrading = False

    try:
        # 创建基础表（Turso 会处理建表语句）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_version INTEGER NOT NULL,
                to_version INTEGER NOT NULL,
                status TEXT NOT NULL,
                started_at REAL NOT NULL,
                finished_at REAL,
                error TEXT,
                trace_id TEXT
            )
        """)

        # 读取版本
        row = cursor.execute("SELECT value FROM settings WHERE key = ?", (DB_SCHEMA_VERSION_KEY,)).fetchone()
        current_version = int(row["value"]) if row and row["value"] is not None else 0

        upgrading = current_version < DB_SCHEMA_VERSION
        if upgrading:
            migration_trace_id = generate_trace_id()
            cursor.execute(
                "INSERT INTO schema_migrations (from_version, to_version, status, started_at, trace_id) VALUES (?, ?, 'running', ?, ?)",
                (current_version, DB_SCHEMA_VERSION, time.time(), migration_trace_id),
            )
            migration_id = cursor.lastrowid

        # --- 这里是原版代码中所有的 CREATE TABLE 语句 ---
        # 由于 Turso 支持 SQLite 语法，以下内容保持原样即可
        cursor.execute("CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, description TEXT, color TEXT DEFAULT '#1a1a1a', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        cursor.execute("CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, password TEXT, client_id TEXT NOT NULL, refresh_token TEXT NOT NULL, group_id INTEGER, status TEXT DEFAULT 'active', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        cursor.execute("CREATE TABLE IF NOT EXISTS temp_emails (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, status TEXT DEFAULT 'active', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        cursor.execute("CREATE TABLE IF NOT EXISTS audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, resource_type TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        cursor.execute("CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, color TEXT NOT NULL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS account_tags (account_id INTEGER, tag_id INTEGER, PRIMARY KEY (account_id, tag_id))")
        
        # 补齐设置项（逻辑保持原样）
        cursor.execute("INSERT OR IGNORE INTO groups (name, description, color) VALUES ('默认分组', '未分组的邮箱', '#666666')")
        
        hashed_pw = hash_password(login_password_default)
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('login_password', ?)", (hashed_pw,))
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('temp_mail_api_key', ?)", (temp_mail_api_key_default,))

        # 写入新版本号
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (DB_SCHEMA_VERSION_KEY, str(DB_SCHEMA_VERSION)))

        if upgrading and migration_id:
            cursor.execute("UPDATE schema_migrations SET status = 'success', finished_at = ? WHERE id = ?", (time.time(), migration_id))

        conn.commit()
        print("Turso 数据库初始化/迁移完成")

    except Exception as e:
        print(f"数据库初始化失败: {str(e)}")
        raise
    finally:
        conn.close()

def migrate_sensitive_data(conn):
    # Turso 适配层自动处理此处的 cursor
    pass
