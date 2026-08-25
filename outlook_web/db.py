from __future__ import annotations

import os
import sqlite3
import time
from typing import Optional

from flask import g

from outlook_web import config
from outlook_web.errors import generate_trace_id, sanitize_error_details
from outlook_web.security.crypto import (
    encrypt_data,
    hash_password,
    is_encrypted,
    is_password_hashed,
)

# 尝试导入 libsql (用于 Turso 云数据库)
try:
    import libsql
except ImportError:
    libsql = None


# =====================================================================
# 手动实现兼容 sqlite3.Row 行为的 Turso/libsql 包装器（解决 row_factory 未实现的问题）
# =====================================================================

class LibsqlRow:
    """完美模拟 sqlite3.Row，支持通过列名 row["value"] 或 索引 row[0] 来读取数据"""
    def __init__(self, col_names: list[str], values: tuple):
        self._col_names = col_names
        self._values = values
        self._dict = {name: val for name, val in zip(col_names, values)}

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        elif isinstance(key, str):
            return self._dict[key]
        else:
            raise TypeError("Row indices must be integers or strings")

    def __iter__(self):
        return iter(self._values)

    def keys(self) -> list[str]:
        return self._col_names

    def __len__(self) -> int:
        return len(self._values)

    def __repr__(self) -> str:
        return f"<Row {self._dict}>"


class LibsqlCursorWrapper:
    """包装 Libsql 的游标，自动将查出来的 tuple 转换为 LibsqlRow"""
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql: str, parameters=()):
        self._cursor.execute(sql, parameters)
        return self

    def executemany(self, sql: str, parameters):
        self._cursor.executemany(sql, parameters)
        return self

    def _wrap_row(self, row):
        if row is None:
            return None
        # 如果有列名描述，才进行包装
        if self._cursor.description:
            col_names = [desc[0] for desc in self._cursor.description]
            return LibsqlRow(col_names, row)
        return row

    def fetchone(self):
        row = self._cursor.fetchone()
        return self._wrap_row(row)

    def fetchall(self):
        rows = self._cursor.fetchall()
        if not rows:
            return []
        if self._cursor.description:
            col_names = [desc[0] for desc in self._cursor.description]
            return [LibsqlRow(col_names, r) for r in rows]
        return rows

    def fetchmany(self, size=None):
        if size is None:
            rows = self._cursor.fetchmany()
        else:
            rows = self._cursor.fetchmany(size)
        if not rows:
            return []
        if self._cursor.description:
            col_names = [desc[0] for desc in self._cursor.description]
            return [LibsqlRow(col_names, r) for r in rows]
        return rows

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def close(self):
        self._cursor.close()

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class LibsqlConnectionWrapper:
    """包装 Libsql 的连接，支持原生 .execute() 等便利方法"""
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return LibsqlCursorWrapper(self._conn.cursor())

    def execute(self, sql: str, parameters=()):
        cursor = self.cursor()
        cursor.execute(sql, parameters)
        return cursor

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)

# =====================================================================


# 数据库 Schema 版本（用于升级可验证/可诊断）
DB_SCHEMA_VERSION = 24
DB_SCHEMA_VERSION_KEY = "db_schema_version"
DB_SCHEMA_LAST_UPGRADE_TRACE_ID_KEY = "db_schema_last_upgrade_trace_id"
DB_SCHEMA_LAST_UPGRADE_ERROR_KEY = "db_schema_last_upgrade_error"


def create_sqlite_connection(database_path: Optional[str] = None) -> any:
    """创建连接（支持本地 SQLite 或云端 Turso）"""
    turso_url = os.getenv("TURSO_URL")
    turso_token = os.getenv("TURSO_TOKEN")

    # 如果配置了 TURSO_URL 且 libsql 模块导入成功，则连接到 Turso
    if turso_url and libsql is not None:
        # 将 None 安全地转换为 "" (空字符串)，避免 libsql 库底层 Rust 类型转换崩溃
        safe_token = turso_token or ""
        print(f"[Database] 检测到配置，正在连接到 Turso 云数据库: {turso_url}")
        if not turso_token:
            print("[Database] ⚠️ 警告：检测到配置了 TURSO_URL，但环境变量中未发现 TURSO_TOKEN！")

        conn_raw = libsql.connect(turso_url, auth_token=safe_token)
        # 核心：使用自定义的包装器来提供 Row 映射支持
        conn = LibsqlConnectionWrapper(conn_raw)
    else:
        # 否则回退到原生本地 SQLite 模式
        path = database_path or config.get_database_path()
        conn = sqlite3.connect(path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
        except Exception:
            pass
        try:
            conn.execute("PRAGMA busy_timeout = 5000")
        except Exception:
            pass
    return conn


def get_db() -> any:
    """获取数据库连接（绑定 to flask.g 生命周期）"""
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
    """向 Flask app 注册 teardown，保证请求结束释放连接"""
    app.teardown_appcontext(close_db)


def init_db(database_path: Optional[str] = None):
    """初始化数据库（含升级记录与可验证状态）"""
    path = database_path or config.get_database_path()
    login_password_default = config.get_login_password_default()
    temp_mail_api_key_default = config.get_temp_mail_api_key_default()

    db_existed = False
    try:
        db_existed = os.path.exists(path) and os.path.getsize(path) > 0
    except Exception:
        db_existed = False

    conn = create_sqlite_connection(path)
    cursor = conn.cursor()

    # 基础并发配置（对既存数据库同样生效。注意：如果使用了 Turso 云数据库，则直接跳过 WAL 等本地 PRAGMA，因为云端不支持）
    if not os.getenv("TURSO_URL"):
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
        except Exception:
            pass

    migration_id = None
    migration_trace_id = None
    upgrading = False

    try:
        # 获取写锁：避免多进程启动时并发迁移导致的偶发失败
        cursor.execute("BEGIN IMMEDIATE")

        # 创建设置表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

        # 数据库迁移记录（用于升级可验证/可诊断）
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
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_schema_migrations_started_at
            ON schema_migrations(started_at)
            """)

        # 在锁内读取当前 schema 版本（保证一致性）
        row = cursor.execute("SELECT value FROM settings WHERE key = ?", (DB_SCHEMA_VERSION_KEY,)).fetchone()
        current_version = int(row["value"]) if row and row["value"] is not None else 0

        upgrading = current_version < DB_SCHEMA_VERSION
        if upgrading:
            migration_trace_id = generate_trace_id()
            if db_existed:
                try:
                    print("=" * 60)
                    print(f"[升级提示] 检测到数据库需要升级：v{current_version} -> v{DB_SCHEMA_VERSION}")
                    print(f"[升级提示] 强烈建议先备份数据库文件：{path}")
                    print(f'[升级提示] 示例：cp "{path}" "{path}.backup"')
                    print(f"[升级提示] trace_id={migration_trace_id}")
                    print("=" * 60)
                except Exception:
                    pass

            cursor.execute(
                """
                INSERT INTO schema_migrations (from_version, to_version, status, started_at, trace_id)
                VALUES (?, ?, 'running', ?, ?)
            """,
                (current_version, DB_SCHEMA_VERSION, time.time(), migration_trace_id),
            )
            migration_id = cursor.lastrowid
            cursor.execute("SAVEPOINT migration_work")

        # -------------------- Schema 创建/迁移（幂等） --------------------

        # 分组表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                color TEXT DEFAULT '#1a1a1a',
                proxy_url TEXT,
                is_system INTEGER DEFAULT 0,
                verification_code_length TEXT DEFAULT '6-6',
                verification_code_regex TEXT DEFAULT '',
                verification_ai_enabled INTEGER DEFAULT 0,
                verification_ai_model TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 邮箱账号表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password TEXT,
                client_id TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                account_type TEXT DEFAULT 'outlook',
                provider TEXT DEFAULT 'outlook',
                imap_host TEXT,
                imap_port INTEGER DEFAULT 993,
                imap_password TEXT,
                group_id INTEGER,
                remark TEXT,
                status TEXT DEFAULT 'active',
                last_refresh_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES groups (id)
            )
        """)

        # 临时邮箱表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS temp_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                status TEXT DEFAULT 'active',
                mailbox_type TEXT NOT NULL DEFAULT 'user',
                visible_in_ui INTEGER NOT NULL DEFAULT 1,
                source TEXT NOT NULL DEFAULT 'custom_domain_temp_mail',
                prefix TEXT,
                domain TEXT,
                task_token TEXT UNIQUE,
                consumer_key TEXT,
                caller_id TEXT,
                task_id TEXT,
                finished_at TIMESTAMP,
                meta_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 临时邮件表（本地缓存，按邮箱地址 + message_id 维度唯一）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS temp_email_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT NOT NULL,
                email_address TEXT NOT NULL,
                from_address TEXT,
                subject TEXT,
                content TEXT,
                html_content TEXT,
                has_html INTEGER DEFAULT 0,
                timestamp INTEGER,
                raw_content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (email_address) REFERENCES temp_emails (email),
                UNIQUE(email_address, message_id)
            )
            """)

        # 刷新运行记录
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account_refresh_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                account_email TEXT NOT NULL,
                refresh_type TEXT DEFAULT 'manual',
                status TEXT NOT NULL,
                error_message TEXT,
                run_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES accounts (id) ON DELETE CASCADE
            )
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_account_refresh_logs_run_id
            ON account_refresh_logs(run_id)
            """)

        # 审计日志表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT,
                user_ip TEXT,
                operator TEXT,
                status TEXT DEFAULT '',
                details TEXT,
                trace_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_logs_trace_id
            ON audit_logs(trace_id)
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at
            ON audit_logs(created_at)
            """)
        cursor.execute("PRAGMA table_info(audit_logs)")
        audit_logs_columns = [col[1] for col in cursor.fetchall()]
        if "operator" not in audit_logs_columns:
            cursor.execute("ALTER TABLE audit_logs ADD COLUMN operator TEXT")
        if "status" not in audit_logs_columns:
            cursor.execute("ALTER TABLE audit_logs ADD COLUMN status TEXT DEFAULT ''")

        # 标签表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                color TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

        # 账号标签关联表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account_tags (
                account_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (account_id, tag_id),
                FOREIGN KEY (account_id) REFERENCES accounts (id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
            )
            """)

        # 分布式锁（用于刷新冲突控制/多进程一致性）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS distributed_locks (
                name TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                acquired_at REAL NOT NULL,
                expires_at REAL NOT NULL
            )
            """)

        # 导出二次验证 Token（持久化，支持重启/多进程）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS export_verify_tokens (
                token TEXT PRIMARY KEY,
                ip TEXT,
                user_agent TEXT,
                expires_at REAL NOT NULL,
                created_at REAL NOT NULL
            )
            """)

        # 登录速率限制（持久化，支持重启/多进程）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS login_attempts (
                ip TEXT PRIMARY KEY,
                count INTEGER NOT NULL,
                last_attempt_at REAL NOT NULL,
                locked_until_at REAL
            )
            """)

        # 刷新运行记录
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS refresh_runs (
                id TEXT PRIMARY KEY,
                trigger_source TEXT NOT NULL,
                status TEXT NOT NULL,
                requested_by_ip TEXT,
                requested_by_user_agent TEXT,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                finished_at TIMESTAMP,
                total INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                message TEXT,
                trace_id TEXT
            )
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_refresh_runs_started_at
            ON refresh_runs(started_at)
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_refresh_runs_trigger_source
            ON refresh_runs(trigger_source)
            """)

        # 兼容旧 schema：补齐缺失列
        cursor.execute("PRAGMA table_info(accounts)")
        columns = [col[1] for col in cursor.fetchall()]

        if "password" not in columns:
            cursor.execute("ALTER TABLE accounts ADD COLUMN password TEXT")
        if "client_id" not in columns:
            cursor.execute("ALTER TABLE accounts ADD COLUMN client_id TEXT NOT NULL DEFAULT ''")
        if "refresh_token" not in columns:
            cursor.execute("ALTER TABLE accounts ADD COLUMN refresh_token TEXT NOT NULL DEFAULT ''")
        if "group_id" not in columns:
            cursor.execute("ALTER TABLE accounts ADD COLUMN group_id INTEGER DEFAULT 1")
        if "remark" not in columns:
            cursor.execute("ALTER TABLE accounts ADD COLUMN remark TEXT")
        if "status" not in columns:
            cursor.execute("ALTER TABLE accounts ADD COLUMN status TEXT DEFAULT 'active'")
        if "updated_at" not in columns:
            cursor.execute("ALTER TABLE accounts ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        if "last_refresh_at" not in columns:
            cursor.execute("ALTER TABLE accounts ADD COLUMN last_refresh_at TIMESTAMP")
        if "account_type" not in columns:
            cursor.execute("ALTER TABLE accounts ADD COLUMN account_type TEXT DEFAULT 'outlook'")
        if "provider" not in columns:
            cursor.execute("ALTER TABLE accounts ADD COLUMN provider TEXT DEFAULT 'outlook'")
        if "imap_host" not in columns:
            cursor.execute("ALTER TABLE accounts ADD COLUMN imap_host TEXT")
        if "imap_port" not in columns:
            cursor.execute("ALTER TABLE accounts ADD COLUMN imap_port INTEGER DEFAULT 993")
        if "imap_password" not in columns:
            cursor.execute("ALTER TABLE accounts ADD COLUMN imap_password TEXT")
        if "telegram_push_enabled" not in columns:
            cursor.execute("ALTER TABLE accounts ADD COLUMN telegram_push_enabled INTEGER NOT NULL DEFAULT 0")
        if "telegram_last_checked_at" not in columns:
            cursor.execute("ALTER TABLE accounts ADD COLUMN telegram_last_checked_at TEXT DEFAULT NULL")
        if "latest_email_subject" not in columns:
            cursor.execute("ALTER TABLE accounts ADD COLUMN latest_email_subject TEXT DEFAULT ''")
        if "latest_email_from" not in columns:
            cursor.execute("ALTER TABLE accounts ADD COLUMN latest_email_from TEXT DEFAULT ''")
        if "latest_email_folder" not in columns:
            cursor.execute("ALTER TABLE accounts ADD COLUMN latest_email_folder TEXT DEFAULT ''")
        if "latest_email_received_at" not in columns:
            cursor.execute("ALTER TABLE accounts ADD COLUMN latest_email_received_at TEXT DEFAULT ''")
        if "latest_verification_code" not in columns:
            cursor.execute("ALTER TABLE accounts ADD COLUMN latest_verification_code TEXT DEFAULT ''")
        if "latest_verification_folder" not in columns:
            cursor.execute("ALTER TABLE accounts ADD COLUMN latest_verification_folder TEXT DEFAULT ''")
        if "latest_verification_received_at" not in columns:
            cursor.execute("ALTER TABLE accounts ADD COLUMN latest_verification_received_at TEXT DEFAULT ''")

        cursor.execute("PRAGMA table_info(groups)")
        group_columns = [col[1] for col in cursor.fetchall()]
        if "is_system" not in group_columns:
            cursor.execute("ALTER TABLE groups ADD COLUMN is_system INTEGER DEFAULT 0")
        if "proxy_url" not in group_columns:
            cursor.execute("ALTER TABLE groups ADD COLUMN proxy_url TEXT")
        if "verification_code_length" not in group_columns:
            cursor.execute("ALTER TABLE groups ADD COLUMN verification_code_length TEXT DEFAULT '6-6'")
        if "verification_code_regex" not in group_columns:
            cursor.execute("ALTER TABLE groups ADD COLUMN verification_code_regex TEXT DEFAULT ''")
        if "verification_ai_enabled" not in group_columns:
            cursor.execute("ALTER TABLE groups ADD COLUMN verification_ai_enabled INTEGER DEFAULT 0")
        if "verification_ai_model" not in group_columns:
            cursor.execute("ALTER TABLE groups ADD COLUMN verification_ai_model TEXT DEFAULT ''")

        # 回填策略字段默认值（幂等）
        cursor.execute(
            "UPDATE groups SET verification_code_length = '6-6' WHERE verification_code_length IS NULL OR TRIM(verification_code_length) = ''"
        )
        cursor.execute("UPDATE groups SET verification_code_regex = '' WHERE verification_code_regex IS NULL")
        cursor.execute("UPDATE groups SET verification_ai_enabled = 0 WHERE verification_ai_enabled IS NULL")
        cursor.execute("UPDATE groups SET verification_ai_model = '' WHERE verification_ai_model IS NULL")

        cursor.execute("PRAGMA table_info(account_refresh_logs)")
        refresh_log_columns = [col[1] for col in cursor.fetchall()]
        if "run_id" not in refresh_log_columns:
            cursor.execute("ALTER TABLE account_refresh_logs ADD COLUMN run_id TEXT")

        cursor.execute("PRAGMA table_info(temp_emails)")
        temp_email_columns = [col[1] for col in cursor.fetchall()]
        for col_def in [
            ("mailbox_type", "TEXT NOT NULL DEFAULT 'user'"),
            ("visible_in_ui", "INTEGER NOT NULL DEFAULT 1"),
            ("source", "TEXT NOT NULL DEFAULT 'custom_domain_temp_mail'"),
            ("prefix", "TEXT"),
            ("domain", "TEXT"),
            ("task_token", "TEXT"),
            ("consumer_key", "TEXT"),
            ("caller_id", "TEXT"),
            ("task_id", "TEXT"),
            ("finished_at", "TIMESTAMP"),
            ("meta_json", "TEXT"),
        ]:
            if col_def[0] not in temp_email_columns:
                cursor.execute(f"ALTER TABLE temp_emails ADD COLUMN {col_def[0]} {col_def[1]}")

        # P0: task_token 需要唯一约束
        try:
            cursor.execute("UPDATE temp_emails SET task_token = NULL WHERE task_token IS NOT NULL AND TRIM(task_token) = ''")
        except Exception:
            pass
        duplicate_sample = cursor.execute("""
            SELECT task_token, COUNT(*) AS c
            FROM temp_emails
            WHERE task_token IS NOT NULL AND TRIM(task_token) != ''
            GROUP BY task_token
            HAVING COUNT(*) > 1
            LIMIT 5
            """).fetchall()
        if duplicate_sample:
            dup_count_row = cursor.execute("""
                SELECT COUNT(*) AS c
                FROM (
                    SELECT task_token
                    FROM temp_emails
                    WHERE task_token IS NOT NULL AND TRIM(task_token) != ''
                    GROUP BY task_token
                    HAVING COUNT(*) > 1
                )
                """).fetchone()
            dup_count = int(dup_count_row["c"] if dup_count_row and dup_count_row["c"] is not None else 0)
            trace_text = str(migration_trace_id or "").strip()
            sql_hint = (
                "-- 1) 找出重复 task_token\n"
                "SELECT task_token, COUNT(*) AS c\n"
                "FROM temp_emails\n"
                "WHERE task_token IS NOT NULL AND TRIM(task_token) != ''\n"
                "GROUP BY task_token\n"
                "HAVING COUNT(*) > 1;\n\n"
                "-- 2) 查看重复 token 对应的行\n"
                "SELECT id, email, task_token, mailbox_type, status, created_at, updated_at\n"
                "FROM temp_emails\n"
                "WHERE task_token IN (\n"
                "  SELECT task_token\n"
                "  FROM temp_emails\n"
                "  WHERE task_token IS NOT NULL AND TRIM(task_token) != ''\n"
                "  GROUP BY task_token\n"
                "  HAVING COUNT(*) > 1\n"
                ")\n"
                "ORDER BY task_token, id;\n\n"
                "-- 3) 示例：保留第一个，其余置空\n"
                "WITH d AS (\n"
                "  SELECT id, task_token,\n"
                "         ROW_NUMBER() OVER (PARTITION BY task_token ORDER BY id) AS rn\n"
                "  FROM temp_emails\n"
                "  WHERE task_token IS NOT NULL AND TRIM(task_token) != ''\n"
                ")\n"
                "UPDATE temp_emails\n"
                "SET task_token = NULL\n"
                "WHERE id IN (SELECT id FROM d WHERE rn > 1);\n"
            )
            raise Exception(
                "数据库升级被中止：检测到 temp_emails.task_token 存在重复值，无法创建唯一索引。"
                f" duplicate_task_token_count={dup_count or len(duplicate_sample)}"
                + (f" trace_id={trace_text}" if trace_text else "")
                + "\n请先备份数据库并清理重复 task_token 后重试。参考 SQL：\n"
                + sql_hint
            )
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_temp_emails_task_token_unique
            ON temp_emails(task_token)
            """)
        cursor.execute("UPDATE temp_emails SET mailbox_type = 'user' WHERE mailbox_type IS NULL OR TRIM(mailbox_type) = ''")
        cursor.execute("UPDATE temp_emails SET visible_in_ui = 1 WHERE visible_in_ui IS NULL")
        cursor.execute("UPDATE temp_emails SET source = 'legacy_gptmail' WHERE source IS NULL OR TRIM(source) = ''")
        cursor.execute("""
            UPDATE temp_emails
            SET prefix = substr(email, 1, instr(email, '@') - 1)
            WHERE (prefix IS NULL OR TRIM(prefix) = '')
              AND instr(email, '@') > 1
        """)
        cursor.execute("""
            UPDATE temp_emails
            SET domain = substr(email, instr(email, '@') + 1)
            WHERE (domain IS NULL OR TRIM(domain) = '')
              AND instr(email, '@') > 1
        """)

        cursor.execute("PRAGMA table_info(temp_email_messages)")
        temp_email_message_columns = [col[1] for col in cursor.fetchall()]
        if "raw_content" not in temp_email_message_columns:
            cursor.execute("ALTER TABLE temp_email_messages ADD COLUMN raw_content TEXT")
        temp_message_create_sql_row = cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'temp_email_messages'"
        ).fetchone()
        temp_message_create_sql = str(temp_message_create_sql_row[0] if temp_message_create_sql_row else "")
        needs_temp_email_message_rebuild = "UNIQUE(email_address, message_id)" not in temp_message_create_sql
        if needs_temp_email_message_rebuild:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS temp_email_messages_v2 (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT NOT NULL,
                    email_address TEXT NOT NULL,
                    from_address TEXT,
                    subject TEXT,
                    content TEXT,
                    html_content TEXT,
                    has_html INTEGER DEFAULT 0,
                    timestamp INTEGER,
                    raw_content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (email_address) REFERENCES temp_emails (email),
                    UNIQUE(email_address, message_id)
                )
            """)
            cursor.execute("""
                INSERT OR REPLACE INTO temp_email_messages_v2 (
                    message_id, email_address, from_address, subject, content,
                    html_content, has_html, timestamp, raw_content, created_at
                )
                SELECT
                    message_id,
                    email_address,
                    from_address,
                    subject,
                    content,
                    html_content,
                    has_html,
                    timestamp,
                    raw_content,
                    created_at
                FROM temp_email_messages
                ORDER BY id ASC
            """)
            cursor.execute("DROP TABLE temp_email_messages")
            cursor.execute("ALTER TABLE temp_email_messages_v2 RENAME TO temp_email_messages")

        cursor.execute("PRAGMA table_info(audit_logs)")
        audit_columns = [col[1] for col in cursor.fetchall()]
        if "trace_id" not in audit_columns:
            cursor.execute("ALTER TABLE audit_logs ADD COLUMN trace_id TEXT")

        # 默认分组
        cursor.execute("""
            INSERT OR IGNORE INTO groups (name, description, color)
            VALUES ('默认分组', '未分组的邮箱', '#666666')
            """)

        # 临时邮箱分组（系统分组）
        cursor.execute("""
            INSERT OR IGNORE INTO groups (name, description, color, is_system)
            VALUES ('临时邮箱', '自建临时邮箱服务', '#00bcf2', 1)
            """)
        cursor.execute("""
            UPDATE groups
            SET description = '自建临时邮箱服务'
            WHERE name = '临时邮箱' AND description IN ('GPTMail 临时邮箱服务', '临时邮箱服务')
            """)

        # 初始化默认设置：登录密码（自动迁移明文 -> 哈希）
        cursor.execute("SELECT value FROM settings WHERE key = 'login_password'")
        existing_password = cursor.fetchone()
        if existing_password:
            password_value = existing_password[0]
            if password_value and not is_password_hashed(password_value):
                hashed_password = hash_password(password_value)
                cursor.execute(
                    """
                    UPDATE settings SET value = ? WHERE key = 'login_password'
                    """,
                    (hashed_password,),
                )
        else:
            hashed_password = hash_password(login_password_default)
            cursor.execute(
                """
                INSERT INTO settings (key, value)
                VALUES ('login_password', ?)
                """,
                (hashed_password,),
            )

        cursor.execute(
            """
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('gptmail_api_key', ?)
            """,
            (temp_mail_api_key_default,),
        )
        cursor.execute("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('temp_mail_provider', 'custom_domain_temp_mail')
            """)
        cursor.execute(
            """
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('temp_mail_api_base_url', ?)
            """,
            (config.get_temp_mail_base_url(),),
        )
        cursor.execute(
            """
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('temp_mail_api_key', ?)
            """,
            (temp_mail_api_key_default,),
        )
        cursor.execute("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('temp_mail_domains', '[]')
            """)
        cursor.execute("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('temp_mail_default_domain', '')
            """)
        cursor.execute("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('temp_mail_prefix_rules', '{"min_length":1,"max_length":32,"pattern":"^[a-z0-9][a-z0-9._-]*$"}')
            """)

        # v0.3: 设置页面 Tab 重构
        cursor.execute("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('cf_worker_domains', '[]')
            """)
        cursor.execute("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('cf_worker_default_domain', '')
            """)
        cursor.execute("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('cf_worker_prefix_rules', '{"min_length":1,"max_length":32,"pattern":"^[a-z0-9][a-z0-9._-]*$"}')
            """)

        # PRD-00008 / FD-00008：对外开放 API Key
        cursor.execute("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('external_api_key', '')
            """)

        # 验证码 AI 增强（系统级配置）
        cursor.execute("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('verification_ai_enabled', 'false')
            """)
        cursor.execute("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('verification_ai_base_url', '')
            """)
        cursor.execute("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('verification_ai_api_key', '')
            """)
        cursor.execute("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('verification_ai_model', '')
            """)

        # 初始化刷新配置
        cursor.execute("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('refresh_interval_days', '30')
            """)
        cursor.execute("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('refresh_delay_seconds', '5')
            """)
        cursor.execute("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('refresh_cron', '0 2 * * *')
            """)
        cursor.execute("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('use_cron_schedule', 'false')
            """)
        cursor.execute("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('enable_scheduled_refresh', 'true')
            """)

        # 初始化轮询配置
        cursor.execute("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('enable_auto_polling', 'false')
            """)
        cursor.execute("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('polling_interval', '10')
            """)
        cursor.execute("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('polling_count', '5')
        """)
        cursor.execute("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('email_notification_enabled', 'false')
        """)
        cursor.execute("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('email_notification_recipient', '')
        """)

        # 索引（性能基线）
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_accounts_last_refresh_at
            ON accounts(last_refresh_at)
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_accounts_status
            ON accounts(status)
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_accounts_group_id
            ON accounts(group_id)
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_account_refresh_logs_account_id
            ON account_refresh_logs(account_id)
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_account_refresh_logs_account_id_id
            ON account_refresh_logs(account_id, id)
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_account_tags_tag_id
            ON account_tags(tag_id)
            """)

        # v5: Telegram 推送去重日志（BUG-00011 P2）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS telegram_push_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                message_id TEXT NOT NULL,
                pushed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
                UNIQUE(account_id, message_id)
            )
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_telegram_push_log_account_id
            ON telegram_push_log(account_id)
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_telegram_push_log_pushed_at
            ON telegram_push_log(pushed_at)
            """)

        # v13: 统一通知游标表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_cursor_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_key TEXT NOT NULL,
                last_cursor_value TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(channel, source_type, source_key)
            )
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_notification_cursor_states_lookup
            ON notification_cursor_states(channel, source_type, source_key)
            """)

        # v13: 统一通知投递日志
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_delivery_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_key TEXT NOT NULL,
                message_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'sent',
                error_code TEXT DEFAULT '',
                error_message TEXT DEFAULT '',
                delivered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(channel, source_type, source_key, message_id)
            )
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_notification_delivery_logs_lookup
            ON notification_delivery_logs(channel, source_type, source_key, delivered_at)
            """)

        # v6: 对外 API 限流表 + 公网模式默认配置
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS external_api_rate_limits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT NOT NULL,
                minute_bucket INTEGER NOT NULL,
                request_count INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ip_address, minute_bucket)
            )
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ext_rate_ip_bucket
            ON external_api_rate_limits(ip_address, minute_bucket)
            """)
        # P1 默认配置
        for key, default in [
            ("external_api_public_mode", "false"),
            ("external_api_ip_whitelist", "[]"),
            ("external_api_rate_limit_per_minute", "60"),
            ("external_api_disable_wait_message", "false"),
            ("external_api_disable_raw_content", "false"),
        ]:
            cursor.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, default),
            )

        # v7: wait-message 异步探测缓存表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS external_probe_cache (
                id TEXT PRIMARY KEY,
                email_addr TEXT NOT NULL,
                folder TEXT NOT NULL DEFAULT 'inbox',
                from_contains TEXT NOT NULL DEFAULT '',
                subject_contains TEXT NOT NULL DEFAULT '',
                since_minutes INTEGER,
                timeout_seconds INTEGER NOT NULL DEFAULT 30,
                poll_interval INTEGER NOT NULL DEFAULT 5,
                status TEXT NOT NULL DEFAULT 'pending',
                result_json TEXT,
                error_code TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL
            )
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_probe_status
            ON external_probe_cache(status, expires_at)
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_probe_email
            ON external_probe_cache(email_addr, status)
            """)

        # v8: 上游真实探测结果缓存表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS external_upstream_probes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope_type TEXT NOT NULL,
                scope_key TEXT NOT NULL,
                email_addr TEXT NOT NULL DEFAULT '',
                probe_method TEXT NOT NULL DEFAULT '',
                probe_ok INTEGER,
                last_probe_at TEXT NOT NULL DEFAULT '',
                last_probe_error TEXT NOT NULL DEFAULT '',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(scope_type, scope_key)
            )
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_upstream_probe_scope
            ON external_upstream_probes(scope_type, scope_key)
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_upstream_probe_email
            ON external_upstream_probes(email_addr, updated_at)
            """)

        # v9: 对外 API 多 Key 配置表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS external_api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                api_key_encrypted TEXT NOT NULL,
                allowed_emails_json TEXT NOT NULL DEFAULT '[]',
                pool_access INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                last_used_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
        cursor.execute("PRAGMA table_info(external_api_keys)")
        external_api_keys_columns = [col[1] for col in cursor.fetchall()]
        if "pool_access" not in external_api_keys_columns:
            cursor.execute("ALTER TABLE external_api_keys ADD COLUMN pool_access INTEGER NOT NULL DEFAULT 0")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_external_api_keys_enabled
            ON external_api_keys(enabled, updated_at)
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_external_api_keys_name
            ON external_api_keys(name)
            """)

        # v10: 调用方日级使用统计
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS external_api_consumer_usage_daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                consumer_key TEXT NOT NULL,
                consumer_name TEXT NOT NULL DEFAULT '',
                caller_id TEXT NOT NULL DEFAULT '',
                usage_date TEXT NOT NULL DEFAULT '',
                date TEXT NOT NULL DEFAULT '',
                endpoint TEXT NOT NULL DEFAULT '',
                total_count INTEGER NOT NULL DEFAULT 0,
                call_count INTEGER NOT NULL DEFAULT 0,
                success_count INTEGER NOT NULL DEFAULT 0,
                error_count INTEGER NOT NULL DEFAULT 0,
                last_status TEXT NOT NULL DEFAULT '',
                last_used_at TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(consumer_key, usage_date, endpoint)
            )
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_external_api_consumer_usage_daily_key
            ON external_api_consumer_usage_daily(consumer_key, usage_date)
            """)
        cursor.execute("PRAGMA table_info(external_api_consumer_usage_daily)")
        external_usage_columns = [col[1] for col in cursor.fetchall()]
        if "caller_id" not in external_usage_columns:
            cursor.execute("ALTER TABLE external_api_consumer_usage_daily ADD COLUMN caller_id TEXT NOT NULL DEFAULT ''")
        if "date" not in external_usage_columns:
            cursor.execute("ALTER TABLE external_api_consumer_usage_daily ADD COLUMN date TEXT NOT NULL DEFAULT ''")
        if "call_count" not in external_usage_columns:
            cursor.execute("ALTER TABLE external_api_consumer_usage_daily ADD COLUMN call_count INTEGER NOT NULL DEFAULT 0")
        cursor.execute("""
            UPDATE external_api_consumer_usage_daily
            SET caller_id = COALESCE(NULLIF(caller_id, ''), consumer_name, consumer_key),
                date = COALESCE(NULLIF(date, ''), usage_date),
                call_count = CASE
                    WHEN COALESCE(call_count, 0) <= 0 AND COALESCE(total_count, 0) > 0 THEN total_count
                    ELSE COALESCE(call_count, 0)
                END
            """)

        # v11: 邮箱池字段 + account_claim_logs 表
        cursor.execute("PRAGMA table_info(accounts)")
        accounts_columns_v11 = [col[1] for col in cursor.fetchall()]
        for col_def in [
            ("pool_status", "TEXT DEFAULT NULL"),
            ("claimed_by", "TEXT DEFAULT NULL"),
            ("claimed_at", "TEXT DEFAULT NULL"),
            ("lease_expires_at", "TEXT DEFAULT NULL"),
            ("claim_token", "TEXT DEFAULT NULL"),
            ("last_claimed_at", "TEXT DEFAULT NULL"),
            ("last_result", "TEXT DEFAULT NULL"),
            ("last_result_detail", "TEXT DEFAULT NULL"),
            ("success_count", "INTEGER DEFAULT 0"),
            ("fail_count", "INTEGER DEFAULT 0"),
        ]:
            if col_def[0] not in accounts_columns_v11:
                cursor.execute(f"ALTER TABLE accounts ADD COLUMN {col_def[0]} {col_def[1]}")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account_claim_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                claim_token TEXT NOT NULL,
                caller_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                action TEXT NOT NULL,
                result TEXT DEFAULT NULL,
                detail TEXT DEFAULT NULL,
                claimed_at TEXT DEFAULT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_claim_logs_account_id
            ON account_claim_logs(account_id)
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_claim_logs_task_id
            ON account_claim_logs(task_id)
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_claim_logs_claim_token
            ON account_claim_logs(claim_token)
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_accounts_pool_status
            ON accounts(pool_status)
            """)
        cursor.execute("PRAGMA table_info(account_claim_logs)")
        account_claim_log_columns = [col[1] for col in cursor.fetchall()]
        if "claimed_at" not in account_claim_log_columns:
            cursor.execute("ALTER TABLE account_claim_logs ADD COLUMN claimed_at TEXT DEFAULT NULL")
        cursor.execute("""
            UPDATE account_claim_logs
            SET claimed_at = COALESCE(claimed_at, created_at)
            WHERE claimed_at IS NULL
            """)

        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('pool_cooldown_seconds', '86400')")
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('pool_default_lease_seconds', '600')")

        # v17: project-scoped pool reuse
        cursor.execute("PRAGMA table_info(accounts)")
        accounts_columns_v17 = [col[1] for col in cursor.fetchall()]
        if "email_domain" not in accounts_columns_v17:
            cursor.execute("ALTER TABLE accounts ADD COLUMN email_domain TEXT DEFAULT NULL")
        # 回填 email_domain
        cursor.execute("""
            UPDATE accounts
            SET email_domain = LOWER(SUBSTR(email, INSTR(email, '@') + 1))
            WHERE (email_domain IS NULL OR TRIM(email_domain) = '')
              AND INSTR(email, '@') > 1
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_accounts_email_domain
            ON accounts(email_domain COLLATE NOCASE)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account_project_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                consumer_key TEXT NOT NULL,
                project_key TEXT NOT NULL,
                first_claimed_at TEXT NOT NULL,
                last_claimed_at TEXT NOT NULL,
                first_success_at TEXT DEFAULT NULL,
                last_success_at TEXT DEFAULT NULL,
                success_count INTEGER NOT NULL DEFAULT 0,
                UNIQUE(account_id, consumer_key, project_key),
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_account_project_usage_lookup
            ON account_project_usage(consumer_key, project_key)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_account_project_usage_account_id
            ON account_project_usage(account_id)
        """)

        # v17: 给 external_probe_cache 加 baseline_timestamp 列
        cursor.execute("PRAGMA table_info(external_probe_cache)")
        probe_columns_v17 = [col[1] for col in cursor.fetchall()]
        if "baseline_timestamp" not in probe_columns_v17:
            cursor.execute("ALTER TABLE external_probe_cache ADD COLUMN baseline_timestamp INTEGER DEFAULT NULL")

        # v18: CF临时邮箱接入邮箱池
        cursor.execute("PRAGMA table_info(accounts)")
        accounts_columns_v18 = [col[1] for col in cursor.fetchall()]
        if "temp_mail_meta" not in accounts_columns_v18:
            cursor.execute("ALTER TABLE accounts ADD COLUMN temp_mail_meta TEXT")

        # v21: Outlook OAuth 验证码提取渠道记忆
        cursor.execute("PRAGMA table_info(accounts)")
        accounts_columns_v21 = [col[1] for col in cursor.fetchall()]
        if "preferred_verification_channel" not in accounts_columns_v21:
            cursor.execute("ALTER TABLE accounts ADD COLUMN preferred_verification_channel TEXT")

        # v22: 邮箱池项目维度成功复用
        cursor.execute("PRAGMA table_info(accounts)")
        accounts_columns_v22 = [col[1] for col in cursor.fetchall()]
        if "claimed_project_key" not in accounts_columns_v22:
            cursor.execute("ALTER TABLE accounts ADD COLUMN claimed_project_key TEXT DEFAULT NULL")

        cursor.execute("PRAGMA table_info(account_project_usage)")
        project_usage_columns_v22 = [col[1] for col in cursor.fetchall()]
        if "first_success_at" not in project_usage_columns_v22:
            cursor.execute("ALTER TABLE account_project_usage ADD COLUMN first_success_at TEXT DEFAULT NULL")
        if "last_success_at" not in project_usage_columns_v22:
            cursor.execute("ALTER TABLE account_project_usage ADD COLUMN last_success_at TEXT DEFAULT NULL")
        if "success_count" not in project_usage_columns_v22:
            cursor.execute("ALTER TABLE account_project_usage ADD COLUMN success_count INTEGER NOT NULL DEFAULT 0")

        # 一次性数据迁移
        if current_version < 22:
            cursor.execute("""
                UPDATE accounts
                SET pool_status = 'available'
                WHERE pool_status = 'used'
                  AND COALESCE(provider, '') != 'cloudflare_temp_mail'
                  AND COALESCE(account_type, '') != 'temp_mail'
                """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS verification_extract_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                channel TEXT NOT NULL,
                started_at REAL NOT NULL,
                finished_at REAL NOT NULL,
                duration_ms INTEGER NOT NULL,
                result_type TEXT NOT NULL,
                code_found TEXT,
                used_ai INTEGER NOT NULL DEFAULT 0,
                error_code TEXT,
                trace_id TEXT,
                created_at REAL NOT NULL DEFAULT (unixepoch('now'))
            )
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_vel_account_id
            ON verification_extract_logs(account_id)
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_vel_started_at
            ON verification_extract_logs(started_at)
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_vel_channel
            ON verification_extract_logs(channel)
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_vel_result_type
            ON verification_extract_logs(result_type)
            """)

        # v24: 临时邮箱接入邮箱池
        cursor.execute("PRAGMA table_info(temp_emails)")
        temp_email_columns_v24 = [col[1] for col in cursor.fetchall()]
        for col_def in [
            ("pool_status", "TEXT DEFAULT NULL"),
            ("claimed_by", "TEXT DEFAULT NULL"),
            ("claimed_at", "TEXT DEFAULT NULL"),
            ("lease_expires_at", "TEXT DEFAULT NULL"),
            ("claim_token", "TEXT DEFAULT NULL"),
            ("last_claimed_at", "TEXT DEFAULT NULL"),
            ("last_result", "TEXT DEFAULT NULL"),
        ]:
            if col_def[0] not in temp_email_columns_v24:
                cursor.execute(f"ALTER TABLE temp_emails ADD COLUMN {col_def[0]} {col_def[1]}")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_temp_emails_pool_status
            ON temp_emails(pool_status)
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_temp_emails_claim_token
            ON temp_emails(claim_token)
            """)
        cursor.execute("""
            UPDATE temp_emails
            SET domain = substr(email, instr(email, '@') + 1)
            WHERE (domain IS NULL OR domain = '') AND instr(email, '@') > 0
            """)
        cursor.execute("""
            UPDATE temp_emails
            SET prefix = substr(email, 1, instr(email, '@') - 1)
            WHERE (prefix IS NULL OR prefix = '') AND instr(email, '@') > 0
            """)

        # 迁移现有明文数据为加密数据
        migrate_sensitive_data(conn)

        # 升级完成标记
        cursor.execute(
            """
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            (DB_SCHEMA_VERSION_KEY, str(DB_SCHEMA_VERSION)),
        )

        if upgrading and migration_id is not None:
            try:
                cursor.execute("RELEASE SAVEPOINT migration_work")
            except Exception:
                pass
            cursor.execute(
                """
                UPDATE schema_migrations
                SET status = 'success', finished_at = ?, error = NULL
                WHERE id = ?
                """,
                (time.time(), migration_id),
            )
            cursor.execute(
                """
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                """,
                (DB_SCHEMA_LAST_UPGRADE_TRACE_ID_KEY, migration_trace_id),
            )
            cursor.execute(
                """
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, '', CURRENT_TIMESTAMP)
                """,
                (DB_SCHEMA_LAST_UPGRADE_ERROR_KEY,),
            )

        conn.commit()

    except Exception as e:
        error_text = sanitize_error_details(str(e))
        try:
            if upgrading and migration_id is not None:
                try:
                    cursor.execute("ROLLBACK TO SAVEPOINT migration_work")
                    cursor.execute("RELEASE SAVEPOINT migration_work")
                except Exception:
                    pass

                cursor.execute(
                    """
                    UPDATE schema_migrations
                    SET status = 'failed', finished_at = ?, error = ?
                    WHERE id = ?
                    """,
                    (time.time(), error_text, migration_id),
                )
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO settings (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    """,
                    (DB_SCHEMA_LAST_UPGRADE_TRACE_ID_KEY, migration_trace_id),
                )
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO settings (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    """,
                    (DB_SCHEMA_LAST_UPGRADE_ERROR_KEY, error_text),
                )
                conn.commit()
            else:
                conn.rollback()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def migrate_sensitive_data(conn: sqlite3.Connection):
    """迁移现有明文敏感数据为加密数据。"""
    cursor = conn.cursor()
    account_columns = {row[1] for row in cursor.execute("PRAGMA table_info(accounts)").fetchall()}
    has_password = "password" in account_columns
    has_refresh_token = "refresh_token" in account_columns
    has_imap_password = "imap_password" in account_columns

    # 动态构建 SELECT
    select_fields = ["id"]
    select_fields.append("password" if has_password else "NULL AS password")
    select_fields.append("refresh_token" if has_refresh_token else "NULL AS refresh_token")
    select_fields.append("imap_password" if has_imap_password else "NULL AS imap_password")
    cursor.execute(f"SELECT {', '.join(select_fields)} FROM accounts")
    accounts = cursor.fetchall()

    migrated_count = 0
    for account_id, password, refresh_token, imap_password in accounts:
        needs_update = False
        new_password = password
        new_refresh_token = refresh_token
        new_imap_password = imap_password

        # 检查并加密 password
        if password and not is_encrypted(password):
            new_password = encrypt_data(password)
            needs_update = True

        # 检查并加密 refresh_token
        if refresh_token and not is_encrypted(refresh_token):
            new_refresh_token = encrypt_data(refresh_token)
            needs_update = True

        # 检查并加密 imap_password
        if imap_password and not is_encrypted(imap_password):
            new_imap_password = encrypt_data(imap_password)
            needs_update = True

        # 更新数据库
        if needs_update:
            cursor.execute(
                """
                UPDATE accounts
                SET password = ?, refresh_token = ?, imap_password = ?
                WHERE id = ?
                """,
                (new_password, new_refresh_token, new_imap_password, account_id),
            )
            migrated_count += 1

    if migrated_count > 0:
        print(f"已迁移 {migrated_count} 个账号的敏感数据为加密存储")

    # 迁移 settings 表中明文存储 of cf_worker_admin_key
    _SETTINGS_SENSITIVE_KEYS = ["cf_worker_admin_key"]
    for key in _SETTINGS_SENSITIVE_KEYS:
        row = cursor.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if row and row[0] and not is_encrypted(row[0]):
            encrypted_value = encrypt_data(row[0])
            cursor.execute(
                "UPDATE settings SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE key = ?",
                (encrypted_value, key),
            )
            print(f"已迁移 settings.{key} 为加密存储")
