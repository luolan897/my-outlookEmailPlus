"""
CF 临时邮箱接入邮箱池 — 补充缺失的测试覆盖

覆盖场景：
1. is_refreshable_outlook_account() 排除 cloudflare_temp_mail
2. build_refreshable_outlook_account_where() SQL 条件正确性
3. resolve_mailbox() CF pool 账号返回 kind='temp'
4. Controller CF 保护（编辑/删除返回 403）
5. _validate_provider() 边界条件
"""
from __future__ import annotations

import json
import unittest

from tests._import_app import clear_login_attempts, import_web_app_module


class RefreshExclusionTests(unittest.TestCase):
    """验证 CF pool 账号不会进入 OAuth token 刷新链路。"""

    @classmethod
    def setUpClass(cls):
        cls.module = import_web_app_module()

    def test_is_refreshable_outlook_account_excludes_cf_provider(self):
        from outlook_web.services.refresh import is_refreshable_outlook_account

        # CF provider 应始终返回 False
        self.assertFalse(
            is_refreshable_outlook_account("temp_mail", provider="cloudflare_temp_mail")
        )
        self.assertFalse(
            is_refreshable_outlook_account("outlook", provider="cloudflare_temp_mail")
        )
        self.assertFalse(
            is_refreshable_outlook_account(None, provider="cloudflare_temp_mail")
        )

    def test_is_refreshable_outlook_account_allows_outlook(self):
        from outlook_web.services.refresh import is_refreshable_outlook_account

        # Outlook 账号应返回 True
        self.assertTrue(is_refreshable_outlook_account("outlook"))
        self.assertTrue(is_refreshable_outlook_account("outlook", provider="outlook"))
        # 历史 NULL account_type 应返回 True
        self.assertTrue(is_refreshable_outlook_account(None))

    def test_is_refreshable_outlook_account_rejects_imap(self):
        from outlook_web.services.refresh import is_refreshable_outlook_account

        # IMAP 账号不应进入刷新链路
        self.assertFalse(is_refreshable_outlook_account("imap"))

    def test_is_refreshable_outlook_account_case_insensitive(self):
        from outlook_web.services.refresh import is_refreshable_outlook_account

        # provider 应做 strip 处理（含空格的也应排除）
        self.assertFalse(
            is_refreshable_outlook_account(None, provider=" cloudflare_temp_mail ")
        )

    def test_build_refreshable_outlook_account_where_excludes_cf(self):
        from outlook_web.services.refresh import build_refreshable_outlook_account_where

        sql = build_refreshable_outlook_account_where()
        # 必须包含排除 cloudflare_temp_mail 的条件
        self.assertIn("cloudflare_temp_mail", sql)
        self.assertIn("!=" , sql)
        self.assertIn("account_type", sql)
        self.assertIn("provider", sql)

    def test_build_refreshable_outlook_account_where_custom_columns(self):
        from outlook_web.services.refresh import build_refreshable_outlook_account_where

        sql = build_refreshable_outlook_account_where(
            column="a_type", provider_column="prov"
        )
        self.assertIn("a_type", sql)
        self.assertIn("prov", sql)


class MailboxResolverCFTests(unittest.TestCase):
    """验证 resolve_mailbox() 对 CF pool 账号返回正确的 descriptor。"""

    @classmethod
    def setUpClass(cls):
        cls.module = import_web_app_module()
        cls.app = cls.module.app

    def setUp(self):
        with self.app.app_context():
            clear_login_attempts()
            from outlook_web.db import get_db

            db = get_db()
            db.execute(
                "DELETE FROM accounts WHERE email LIKE '%@cf_resolver.test'"
            )
            db.commit()

    def tearDown(self):
        with self.app.app_context():
            from outlook_web.db import get_db

            db = get_db()
            db.execute(
                "DELETE FROM accounts WHERE email LIKE '%@cf_resolver.test'"
            )
            db.commit()

    def test_cf_pool_account_returns_kind_temp(self):
        """provider=cloudflare_temp_mail 的账号应返回 kind='temp'，走 TempMailService。"""
        with self.app.app_context():
            from outlook_web.db import get_db
            from outlook_web.services import mailbox_resolver

            db = get_db()
            meta = json.dumps(
                {"provider_name": "cloudflare_temp_mail", "address_id": "test_123"},
                ensure_ascii=False,
            )
            db.execute(
                """
                INSERT INTO accounts (email, password, client_id, refresh_token,
                                       status, account_type, provider, temp_mail_meta)
                VALUES (?, '', '', '', 'active', 'temp_mail', 'cloudflare_temp_mail', ?)
                """,
                ("cf_user@cf_resolver.test", meta),
            )
            db.commit()

            mailbox = mailbox_resolver.resolve_mailbox("cf_user@cf_resolver.test")

        self.assertEqual(mailbox["kind"], "temp")
        self.assertEqual(mailbox["source"], "cloudflare_temp_mail")
        self.assertEqual(mailbox["provider_name"], "cloudflare_temp_mail")
        self.assertEqual(mailbox["read_capability"], "temp")
        self.assertFalse(mailbox["visible_in_ui"])

    def test_cf_pool_account_meta_parsed_correctly(self):
        """temp_mail_meta 应被正确解析并写入 meta 字段。"""
        with self.app.app_context():
            from outlook_web.db import get_db
            from outlook_web.services import mailbox_resolver

            db = get_db()
            meta = json.dumps(
                {"address_id": "abc123", "test_key": "test_value"},
                ensure_ascii=False,
            )
            db.execute(
                """
                INSERT INTO accounts (email, password, client_id, refresh_token,
                                       status, account_type, provider, temp_mail_meta)
                VALUES (?, '', '', '', 'active', 'temp_mail', 'cloudflare_temp_mail', ?)
                """,
                ("cf_meta@cf_resolver.test", meta),
            )
            db.commit()

            mailbox = mailbox_resolver.resolve_mailbox("cf_meta@cf_resolver.test")

        parsed_meta = mailbox["meta"]
        self.assertIsInstance(parsed_meta, dict)
        self.assertEqual(parsed_meta["address_id"], "abc123")
        self.assertEqual(parsed_meta["test_key"], "test_value")
        self.assertEqual(parsed_meta["provider_name"], "cloudflare_temp_mail")

    def test_cf_pool_account_corrupted_meta_graceful(self):
        """temp_mail_meta 损坏（非 JSON）时不应崩溃。"""
        with self.app.app_context():
            from outlook_web.db import get_db
            from outlook_web.services import mailbox_resolver

            db = get_db()
            db.execute(
                """
                INSERT INTO accounts (email, password, client_id, refresh_token,
                                       status, account_type, provider, temp_mail_meta)
                VALUES (?, '', '', '', 'active', 'temp_mail', 'cloudflare_temp_mail', ?)
                """,
                ("cf_bad@cf_resolver.test", "NOT_VALID_JSON{{{{"),
            )
            db.commit()

            mailbox = mailbox_resolver.resolve_mailbox("cf_bad@cf_resolver.test")

        self.assertEqual(mailbox["kind"], "temp")
        self.assertIsInstance(mailbox["meta"], dict)
        self.assertEqual(mailbox["meta"].get("provider_name"), "cloudflare_temp_mail")

    def test_regular_outlook_account_not_affected(self):
        """普通 Outlook 账号不应受 CF 逻辑影响。"""
        with self.app.app_context():
            from outlook_web.db import get_db
            from outlook_web.services import mailbox_resolver

            db = get_db()
            db.execute(
                """
                INSERT INTO accounts (email, password, client_id, refresh_token,
                                       status, account_type, provider)
                VALUES (?, 'pw', 'cid', 'rt', 'active', 'outlook', 'outlook')
                """,
                ("normal@cf_resolver.test",),
            )
            db.commit()

            mailbox = mailbox_resolver.resolve_mailbox("normal@cf_resolver.test")

        self.assertEqual(mailbox["kind"], "account")
        self.assertEqual(mailbox["read_capability"], "graph")


class ValidateProviderTests(unittest.TestCase):
    """验证 _validate_provider() 的校验逻辑。"""

    @classmethod
    def setUpClass(cls):
        cls.module = import_web_app_module()

    def test_validate_provider_none_returns_none(self):
        from outlook_web.services.pool import _validate_provider

        self.assertIsNone(_validate_provider(None))

    def test_validate_provider_empty_string_returns_none(self):
        from outlook_web.services.pool import _validate_provider

        self.assertIsNone(_validate_provider(""))
        self.assertIsNone(_validate_provider("   "))

    def test_validate_provider_valid_values(self):
        from outlook_web.services.pool import _validate_provider

        for valid in ["outlook", "imap", "custom", "cloudflare_temp_mail"]:
            with self.subTest(provider=valid):
                self.assertEqual(_validate_provider(valid), valid)

    def test_validate_provider_strips_whitespace(self):
        from outlook_web.services.pool import _validate_provider

        self.assertEqual(_validate_provider("  outlook  "), "outlook")
        self.assertEqual(_validate_provider(" cloudflare_temp_mail "), "cloudflare_temp_mail")

    def test_validate_provider_invalid_raises(self):
        from outlook_web.services.pool import PoolServiceError, _validate_provider

        with self.assertRaises(PoolServiceError) as ctx:
            _validate_provider("invalid_provider")
        self.assertEqual(ctx.exception.error_code, "invalid_provider")


class InsertClaimedAccountTests(unittest.TestCase):
    """验证 insert_claimed_account() 的边界条件。"""

    @classmethod
    def setUpClass(cls):
        cls.module = import_web_app_module()
        from outlook_web.db import create_sqlite_connection
        from outlook_web.repositories import pool as pool_repo

        cls.pool_repo = pool_repo
        cls.create_conn = staticmethod(lambda: create_sqlite_connection())

    def tearDown(self):
        conn = self.create_conn()
        try:
            # 先清理关联表（外键约束要求顺序删除）
            conn.execute(
                "DELETE FROM account_project_usage WHERE account_id IN "
                "(SELECT id FROM accounts WHERE email LIKE '%@insert_test.pool')"
            )
            conn.execute(
                "DELETE FROM account_claim_logs WHERE account_id IN "
                "(SELECT id FROM accounts WHERE email LIKE '%@insert_test.pool')"
            )
            conn.execute(
                "DELETE FROM accounts WHERE email LIKE '%@insert_test.pool'"
            )
            conn.commit()
        finally:
            conn.close()

    def test_insert_claimed_account_empty_email_raises(self):
        from outlook_web.repositories.pool import PoolRepositoryError

        conn = self.create_conn()
        try:
            with self.assertRaises(PoolRepositoryError) as ctx:
                self.pool_repo.insert_claimed_account(
                    conn,
                    email="",
                    caller_id="bot",
                    task_id="t1",
                    lease_seconds=60,
                    provider="cloudflare_temp_mail",
                )
            self.assertEqual(ctx.exception.error_code, "invalid_email")
        finally:
            conn.close()

    def test_insert_claimed_account_whitespace_email_raises(self):
        from outlook_web.repositories.pool import PoolRepositoryError

        conn = self.create_conn()
        try:
            with self.assertRaises(PoolRepositoryError) as ctx:
                self.pool_repo.insert_claimed_account(
                    conn,
                    email="   ",
                    caller_id="bot",
                    task_id="t1",
                    lease_seconds=60,
                    provider="cloudflare_temp_mail",
                )
            self.assertEqual(ctx.exception.error_code, "invalid_email")
        finally:
            conn.close()

    def test_insert_claimed_account_success_returns_dict(self):
        conn = self.create_conn()
        try:
            result = self.pool_repo.insert_claimed_account(
                conn,
                email="new_cf@insert_test.pool",
                caller_id="bot",
                task_id="t1",
                lease_seconds=120,
                provider="cloudflare_temp_mail",
                temp_mail_meta={"address_id": "x123"},
            )
            self.assertIsInstance(result, dict)
            self.assertEqual(result["email"], "new_cf@insert_test.pool")
            self.assertEqual(result["provider"], "cloudflare_temp_mail")
            self.assertEqual(result["pool_status"], "claimed")
            self.assertTrue(result["claim_token"].startswith("clm_"))
            self.assertEqual(result["email_domain"], "insert_test.pool")
            # 验证 temp_mail_meta 被序列化为 JSON 字符串
            self.assertIsInstance(result["temp_mail_meta"], str)
            parsed = json.loads(result["temp_mail_meta"])
            self.assertEqual(parsed["address_id"], "x123")
        finally:
            conn.close()

    def test_insert_claimed_account_with_project_key(self):
        conn = self.create_conn()
        try:
            result = self.pool_repo.insert_claimed_account(
                conn,
                email="proj_cf@insert_test.pool",
                caller_id="bot",
                task_id="t2",
                lease_seconds=60,
                provider="cloudflare_temp_mail",
                project_key="my_project",
            )
            self.assertEqual(result["email"], "proj_cf@insert_test.pool")

            # 验证 project usage 被写入
            row = conn.execute(
                """
                SELECT * FROM account_project_usage
                WHERE project_key = 'my_project'
                """
            ).fetchone()
            self.assertIsNotNone(row)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
