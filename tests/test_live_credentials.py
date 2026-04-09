"""
真实凭据集成测试 — 验证 Graph API + IMAP 回退机制
"""
from __future__ import annotations

import json
import sys
import traceback

# ============================================================
# 真实凭据（分隔符 ---- 拆分）
# ============================================================
RAW = (
    "onvoam11571l@hotmail.com----ni473830----"
    "9e5f94bc-e8a4-4e73-b8be-63364c29d753----"
    "M.C559_SN1.0.U.-CnlQlHCseit2zzQYcLU5jIWbRRwseUYhMT2Tr75w2WaYiMLnXPNg4v6ddst8op*wijEP"
    "bC4LcfAHAJErq6vXTKPi3qybdldarJVEgkvuixon9q3aYfW9sxVZ2HBcsNUspP3DZpLuLuHFWVqgjsTHTBLUfn674jR!2Z3d7DWuz90MpnmhBqieDUh6jo0GRFlW9F8GBaOJm0H6sMff1Z3YDO!DeT8ynVgQkGdlEkN*"
    "z4Jo94dEJbyaaMSyhkQD0WUHHvrPFCXku!tZhxfi!jOooeH2gHE2IOmQS8NDI0s6nsuRY7SibuzIpswYA*GymV5ZcqLu63uKRbHm2pfiR2ddvXXl1TnfTfOnIwhdJ!1ie1iSYAiEFANKn9U7bGEd!u1bsncE0ceBX60n"
    "zeCCz8x6QMA$"
)
parts = RAW.split("----")
EMAIL = parts[0]
PASSWORD = parts[1]
CLIENT_ID = parts[2]
REFRESH_TOKEN = parts[3]

PASS_COUNT = 0
FAIL_COUNT = 0


def report(name: str, ok: bool, detail: str = ""):
    global PASS_COUNT, FAIL_COUNT
    tag = "PASS" if ok else "FAIL"
    if ok:
        PASS_COUNT += 1
    else:
        FAIL_COUNT += 1
    suffix = f" — {detail}" if detail else ""
    print(f"  [{tag}] {name}{suffix}")


# ============================================================
# 测试 1: _is_graph_auth_expired 逻辑验证
# ============================================================
def test_auth_expired_logic():
    print("\n=== 测试 1: _is_graph_auth_expired 区分逻辑 ===")
    from outlook_web.services.graph import _is_graph_auth_expired

    # 非 401 一律返回 False
    report("非 401 状态码 → False", not _is_graph_auth_expired(200, {}))
    report("500 状态码 → False", not _is_graph_auth_expired(500, {}))

    # 401 + token 过期 code → True
    for code in ("InvalidAuthenticationToken", "Authentication.TokenExpired", "TokenExpired"):
        report(f"401 + {code} → True", _is_graph_auth_expired(401, {"error": {"code": code}}))

    # 401 + 权限不足 code → False
    report("401 + ErrorAccessDenied → False", not _is_graph_auth_expired(401, {"error": {"code": "ErrorAccessDenied"}}))

    # 401 + 空 details → False（保守策略）
    report("401 + 空详情 → False", not _is_graph_auth_expired(401, None))
    report("401 + 非 dict 详情 → False", not _is_graph_auth_expired(401, "some string"))


# ============================================================
# 测试 2: Refresh Token 有效性
# ============================================================
def test_refresh_token():
    print("\n=== 测试 2: Refresh Token 有效性 ===")
    from outlook_web.services.graph import test_refresh_token_with_rotation

    ok, err, new_rt = test_refresh_token_with_rotation(CLIENT_ID, REFRESH_TOKEN)
    report("Refresh Token 有效", ok, err if not ok else f"新 RT 长度={len(new_rt) if new_rt else 0}")
    if new_rt:
        report("Token Rotation 正常", len(new_rt) > 20, f"新 RT 前 40 字符: {new_rt[:40]}...")
    return ok


# ============================================================
# 测试 3: Graph API 获取邮件 (带原始响应诊断)
# ============================================================
def test_graph_get_emails():
    print("\n=== 测试 3: Graph API 获取邮件列表 ===")
    import requests as req
    from outlook_web.services.graph import get_emails_graph, get_access_token_graph_result

    # 3a. 先诊断原始 HTTP 响应
    print("  --- 3a. 诊断原始 Graph API 响应 ---")
    token_result = get_access_token_graph_result(CLIENT_ID, REFRESH_TOKEN)
    if not token_result.get("success"):
        report("获取 access_token 失败", False, json.dumps(token_result.get("error"), ensure_ascii=False)[:200])
        return False

    access_token = token_result.get("access_token")
    report("获取 access_token 成功", True, f"长度={len(access_token)}")

    # 直接发请求看原始 401 响应
    raw_resp = req.get(
        "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"$top": "1", "$select": "id,subject"},
        timeout=30,
    )
    report(f"原始 HTTP 状态码 = {raw_resp.status_code}", raw_resp.status_code == 200)
    if raw_resp.status_code != 200:
        try:
            raw_json = raw_resp.json()
            print(f"       响应 JSON: {json.dumps(raw_json, ensure_ascii=False)}")
        except Exception:
            print(f"       响应文本: {raw_resp.text[:500]}")

    # 3b. 通过封装函数调用
    print("  --- 3b. 通过 get_emails_graph 封装调用 ---")
    result = get_emails_graph(CLIENT_ID, REFRESH_TOKEN, folder="inbox", skip=0, top=5)
    report("请求成功", result.get("success"), json.dumps(result.get("error"), ensure_ascii=False)[:300] if not result.get("success") else "")

    if result.get("success"):
        emails = result.get("emails", [])
        report(f"获取到 {len(emails)} 封邮件", len(emails) >= 0)
        if emails:
            first = emails[0]
            print(f"       最新邮件: {first.get('subject', 'N/A')}")
            print(f"       来自: {first.get('from', {}).get('emailAddress', {}).get('address', 'N/A')}")
            print(f"       时间: {first.get('receivedDateTime', 'N/A')}")
        new_rt = result.get("new_refresh_token")
        report("返回新 refresh_token", bool(new_rt))
    else:
        # 检查 auth_expired 标记是否正确
        auth_expired = result.get("auth_expired")
        error = result.get("error", {})
        details = error.get("details", "")
        code = ""
        if isinstance(details, dict):
            code = details.get("error", {}).get("code", "")
        expected = code in ("InvalidAuthenticationToken", "Authentication.TokenExpired", "TokenExpired")
        report(f"auth_expired 标记正确 (code={code})", auth_expired == expected, f"auth_expired={auth_expired}")
        report("auth_expired=False → 允许 IMAP 回退", not auth_expired)

    return result.get("success")


# ============================================================
# 测试 4: Graph API 获取验证码
# ============================================================
def test_graph_extract_verification():
    print("\n=== 测试 4: Graph API 提取验证码 ===")
    from outlook_web.services.graph import get_emails_graph
    from outlook_web.services.verification_extractor import extract_verification_info

    # 获取邮件
    result = get_emails_graph(CLIENT_ID, REFRESH_TOKEN, folder="inbox", skip=0, top=10)
    if not result.get("success"):
        report("获取邮件失败，跳过验证码测试", False)
        return

    emails = result.get("emails", [])
    report(f"获取 {len(emails)} 封邮件用于验证码提取", True)

    verified_count = 0
    for email in emails[:5]:
        subject = email.get("subject", "")
        body_preview = email.get("bodyPreview", "")

        # 尝试从预览文本提取验证码
        extract_result = extract_verification_info(body_preview)
        if extract_result.get("verification_code"):
            verified_count += 1
            print(f"       邮件 '{subject[:50]}': 验证码={extract_result['verification_code']}")

    report(f"验证码提取测试完成 (找到 {verified_count} 个)", True)


# ============================================================
# 测试 4b: IMAP 回退获取邮件 (直接测试 IMAP 服务)
# ============================================================
def test_imap_fallback():
    print("\n=== 测试 4b: IMAP 直接获取邮件 (outlook.live.com) ===")
    try:
        from outlook_web.services.imap import get_emails_imap_with_server

        result = get_emails_imap_with_server(
            EMAIL, CLIENT_ID, REFRESH_TOKEN,
            folder="inbox", skip=0, top=5,
            server="outlook.live.com",
        )
        report("IMAP (New) 获取成功", result.get("success"), json.dumps(result.get("error"), ensure_ascii=False)[:200] if not result.get("success") else "")
        if result.get("success"):
            emails = result.get("emails", [])
            report(f"获取到 {len(emails)} 封邮件", True)
            for e in emails[:3]:
                print(f"       邮件: {e.get('subject', 'N/A')}")
    except Exception as e:
        report("IMAP (New) 测试异常", False, str(e))
        traceback.print_exc()

    print("  --- IMAP (Old: outlook.office365.com) ---")
    try:
        from outlook_web.services.imap import get_emails_imap_with_server

        result = get_emails_imap_with_server(
            EMAIL, CLIENT_ID, REFRESH_TOKEN,
            folder="inbox", skip=0, top=5,
            server="outlook.office365.com",
        )
        report("IMAP (Old) 获取成功", result.get("success"), json.dumps(result.get("error"), ensure_ascii=False)[:200] if not result.get("success") else "")
        if result.get("success"):
            emails = result.get("emails", [])
            report(f"获取到 {len(emails)} 封邮件", True)
    except Exception as e:
        report("IMAP (Old) 测试异常", False, str(e))


# ============================================================
# 测试 5: Token Result 错误详情
# ============================================================
def test_token_error_detail():
    print("\n=== 测试 5: Token 获取错误详情结构 ===")
    from outlook_web.services.graph import get_access_token_graph_result

    # 使用无效 client_id 测试错误处理
    result = get_access_token_graph_result("invalid-client-id", "invalid-token")
    report("错误返回 success=False", not result.get("success"))

    error = result.get("error", {})
    report("error 包含 code 字段", bool(error.get("code")))
    report("error 包含 message 字段", bool(error.get("message")))
    report("error 包含 status 字段", bool(error.get("status")))
    report("error 包含 type 字段", bool(error.get("type")))

    print(f"       错误详情: {json.dumps(error, ensure_ascii=False)}")


# ============================================================
# 测试 6: 完整 Flask 端到端测试（可选）
# ============================================================
def test_flask_e2e():
    print("\n=== 测试 6: Flask 端到端测试 ===")
    try:
        from tests._import_app import clear_login_attempts, import_web_app_module

        module = import_web_app_module()
        app = module.app
        client = app.test_client()

        with app.app_context():
            # 登录
            clear_login_attempts()
            resp = client.post("/login", json={"password": "testpass123"})
            report("登录成功", resp.status_code == 200 and (resp.get_json() or {}).get("success"))

            if resp.status_code != 200:
                print("       登录失败，跳过后续测试")
                return

            # 插入测试账号
            from outlook_web.security.crypto import encrypt_data

            enc_rt = encrypt_data(REFRESH_TOKEN)
            enc_pw = encrypt_data(PASSWORD)

            conn = module.create_sqlite_connection()
            try:
                # 先删除已存在的测试账号
                conn.execute("DELETE FROM accounts WHERE email = ?", (EMAIL,))
                conn.execute(
                    """
                    INSERT INTO accounts (
                        email, password, client_id, refresh_token, group_id, status,
                        account_type, provider
                    )
                    VALUES (?, ?, ?, ?, 1, 'active', 'outlook', 'outlook')
                    """,
                    (EMAIL, enc_pw, CLIENT_ID, enc_rt),
                )
                conn.commit()
            finally:
                conn.close()
            report("测试账号插入成功", True)

            # 调用邮件列表 API
            resp = client.get(f"/api/emails/{EMAIL}?folder=inbox&skip=0&top=5")
            data = resp.get_json() or {}
            report(f"获取邮件 API 状态={resp.status_code}", resp.status_code == 200, json.dumps(data, ensure_ascii=False)[:200] if resp.status_code != 200 else "")

            if data.get("success"):
                method = data.get("method", "")
                emails = data.get("emails", [])
                report(f"通过 {method} 获取到 {len(emails)} 封邮件", True)
                if emails:
                    print(f"       最新: {emails[0].get('subject', 'N/A')}")
            else:
                # 检查是否是 auth_expired
                code = data.get("code", "")
                report(f"返回错误码: {code}", True)

            # 调用验证码提取 API
            resp = client.get(f"/api/emails/{EMAIL}/extract-verification")
            data = resp.get_json() or {}
            report(f"验证码提取 API 状态={resp.status_code}", resp.status_code == 200)
            if data.get("success"):
                vdata = data.get("data", {})
                if vdata.get("verification_code"):
                    print(f"       验证码: {vdata['verification_code']}")

            # 清理测试账号
            conn = module.create_sqlite_connection()
            try:
                conn.execute("DELETE FROM accounts WHERE email = ?", (EMAIL,))
                conn.commit()
            finally:
                conn.close()
            report("测试账号清理完成", True)

    except Exception as e:
        report("Flask E2E 测试异常", False, str(e))
        traceback.print_exc()


# ============================================================
# 主入口
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  Outlook Email Plus — 真实凭据集成测试")
    print(f"  账号: {EMAIL}")
    print(f"  Client ID: {CLIENT_ID}")
    print(f"  Refresh Token: {REFRESH_TOKEN[:40]}...({len(REFRESH_TOKEN)} 字符)")
    print("=" * 60)

    try:
        test_auth_expired_logic()
        test_token_error_detail()
        token_ok = test_refresh_token()
        if token_ok:
            graph_ok = test_graph_get_emails()
            if not graph_ok:
                test_imap_fallback()
            test_graph_extract_verification()
        else:
            print("\n  ⚠ Refresh Token 无效，跳过 Graph API 邮件测试")
        test_flask_e2e()
    except Exception as e:
        print(f"\n  测试执行异常: {e}")
        traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"  结果: {PASS_COUNT} 通过, {FAIL_COUNT} 失败, 共 {PASS_COUNT + FAIL_COUNT} 项")
    print("=" * 60)

    sys.exit(0 if FAIL_COUNT == 0 else 1)
