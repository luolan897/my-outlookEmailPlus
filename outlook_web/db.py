from __future__ import annotations
import os
import time
import re
from typing import Optional, Any
from flask import g
import libsql_client
from outlook_web import config
from outlook_web.security.crypto import hash_password

# 核心常量定义
DB_SCHEMA_VERSION = 23
DB_SCHEMA_VERSION_KEY = "db_schema_version"
DB_SCHEMA_LAST_UPGRADE_TRACE_ID_KEY = "db_schema_last_upgrade_trace_id"
DB_SCHEMA_LAST_UPGRADE_ERROR_KEY = "db_schema_last_upgrade_error"

class TursoRow(dict):
    def __init__(self, columns: list[str], values: list):
        self._columns = columns
        self._values = values
        super().__init__(zip(columns, values))
    def __getitem__(self, key):
        if isinstance(key, int): return self._values[key] if key < len(self._values) else None
        return super().get(key)
    def __getattr__(self, name: str) -> Any:
        if name in self: return self[name]
        return None
    def __iter__(self): return iter(self._values)
    def __len__(self): return len(self._values)
    def keys(self): return self._columns

class TursoCursor:
    def __init__(self, client):
        self.client = client
        self.last_result = None
        self.lastrowid = None
        self.rowcount = 0
        self._columns = []
        self._pos = 0

    def execute(self, sql: str, params: Any = None):
        raw_sql = sql.strip()
        upper_sql = raw_sql.upper()

        # 1. 模拟 PRAGMA (项目自检结构的关键)
        if "PRAGMA TABLE_INFO" in upper_sql:
            table_name = re.search(r"TABLE_INFO\((.*?)\)", upper_sql).group(1).strip("'\" ")
            try:
                res = self.client.execute(f"SELECT * FROM {table_name} LIMIT 0")
                fake_rows = [[i, col, 'TEXT', 0, None, 0] for i, col in enumerate(res.columns)]
                from types import SimpleNamespace
                self.last_result = SimpleNamespace(columns=['cid', 'name', 'type', 'notnull', 'dflt_value', 'pk'], rows=fake_rows)
                self._columns = self.last_result.columns
                self._pos = 0
                return self
            except:
                self.last_result = None
                return self

        # 2. 物理指令拦截
        if any(upper_sql.startswith(p) for p in ["PRAGMA", "BEGIN", "SAVEPOINT", "RELEASE", "ROLLBACK"]):
            return self
        
        # 3. 语法适配
        sql_to_run = raw_sql
        if "INSERT OR IGNORE" in upper_sql:
            sql_to_run = re.sub(r"INSERT\s+OR\s+IGNORE\s+INTO", "INSERT INTO", raw_sql, flags=re.IGNORECASE) + " ON CONFLICT DO NOTHING"
        elif "INSERT OR REPLACE" in upper_sql:
            sql_to_run = re.sub(r"INSERT\s+OR\s+REPLACE\s+INTO", "REPLACE INTO", raw_sql, flags=re.IGNORECASE)

        p = list(params) if params else []
        try:
            res = self.client.execute(sql_to_run, p)
            self.last_result = res
            # 【重要】确保返回整数类型的 ID，否则添加账户后程序会认为失败
            self.lastrowid = int(res.last_insert_rowid) if res.last_insert_rowid is not None else None
            self.rowcount = getattr(res, "rows_affected", 0)
            self._columns = list(getattr(res, "columns", []))
            self._pos = 0
        except KeyError as e:
            if str(e) == "'result'":
                self.rowcount = 1
                return self
            raise e
        except Exception as e:
            if "UNIQUE constraint failed" in str(e) or "already exists" in str(e):
                self.rowcount = 0
                return self
            if "settings" not in upper_sql:
                print(f"❌ SQL Error: {e} | SQL: {raw_sql[:100]}")
            raise e
        return self

    def fetchone(self):
        if not self.last_result or not hasattr(self.last_result, "rows") or self._pos >= len(self.last_result.rows):
            return None
        row = self.last_result.rows[self._pos]
        self._pos += 1
        return TursoRow(self._columns, row)

    def fetchall(self):
        if not self.last_result or not hasattr(self.last_result, "rows"): return []
        return [TursoRow(self._columns, r) for r in self.last_result.rows]

    def __iter__(self):
        while True:
            row = self.fetchone()
            if row is None: break
            yield row
    def close(self): pass

class TursoConnection:
    def __init__(self):
        raw_url = os.environ.get("TURSO_URL", "").strip()
        self.url = raw_url.replace("libsql://", "https://").replace("wss://", "https://")
        if not self.url.startswith("https://"): self.url = f"https://{self.url}"
        self.token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
        self.client = libsql_client.create_client_sync(self.url, auth_token=self.token)

    def cursor(self): return TursoCursor(self.client)
    def execute(self, sql, params=None): return self.cursor().execute(sql, params)
    def __enter__(self): return self
    def __exit__(self, exc_type, exc_val, exc_tb): self.close()
    def commit(self): pass
    def rollback(self): pass
    def close(self):
        try: self.client.close()
        except: pass

# --- Flask 接口 ---
def create_sqlite_connection(_path=None): return TursoConnection()
def get_db():
    if '_database' not in g: g._database = create_sqlite_connection()
    return g._database
def close_db(e=None):
    db = g.pop('_database', None)
    if db is not None: db.close()
def register_db(app): app.teardown_appcontext(close_db)

def init_db(database_path: Optional[str] = None):
    try:
        with create_sqlite_connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            res = db.execute("SELECT value FROM settings WHERE key = ?", (DB_SCHEMA_VERSION_KEY,))
            row = res.fetchone()
            if not row:
                print("--- 正在执行云端初始化 ---")
                db.execute("CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, description TEXT, color TEXT DEFAULT '#1a1a1a')")
                db.execute("INSERT OR IGNORE INTO groups (name) VALUES ('默认分组')")
                pw = hash_password(config.get_login_password_default())
                db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('login_password', ?)", (pw,))
                db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (DB_SCHEMA_VERSION_KEY, str(DB_SCHEMA_VERSION)))
    except Exception as e: print(f"⚠ Init Check Notice: {e}")

def migrate_sensitive_data(conn): pass
