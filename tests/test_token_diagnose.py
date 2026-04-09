"""
Token 逐步诊断脚本 — 逐层排查 Graph API / IMAP 的问题
"""
import json
import sys
import traceback

# 凭据
EMAIL = "onvoam11571l@hotmail.com"
PASSWORD = "ni473830"
CLIENT_ID = "9e5f94bc-e8a4-4e73-b8be-63364c29d753"
REFRESH_TOKEN = (
    "M.C559_SN1.0.U.-CnlQlHCseit2zzQYcLU5jIWbRRwseUYhMT2Tr75w2WaYiMLnXPNg4v6ddst8op*wijEP"
    "bC4LcfAHAJErq6vXTKPi3qybdldarJVEgkvuixon9q3aYfW9sxVZ2HBcsNUspP3DZpLuLuHFWVqgjsTHTBLUfn674jR!2Z3d7DWuz90MpnmhBqieDUh6jo0GRFlW9F8GBaOJm0H6sMff1Z3YDO!DeT8ynVgQkGdlEkN*"
    "z4Jo94dEJbyaaMSyhkQD0WUHHvrPFCXku!tZhxfi!jOooeH2gHE2IOmQS8NDI0s6nsuRY7SibuzIpswYA*GymV5ZcqLu63uKRbHm2pfiR2ddvXXl1TnfTfOnIwhdJ!1ie1iSYAiEFANKn9U7bGEd!u1bsncE0ceBX60n"
    "zeCCz8x6QMA$"
)

TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def ok(msg):
    print(f"  [OK]   {msg}")


def fail(msg, detail=""):
    print(f"  [FAIL] {msg}")
    if detail:
        print(f"         {detail}")


def info(msg):
    print(f"  [INFO] {msg}")


# ============================================================
section("第 1 步: Token 刷新 — 原始 HTTP 请求")
# ============================================================
print(f"  Email:    {EMAIL}")
print(f"  ClientID: {CLIENT_ID}")
print(f"  RT 长度:  {len(REFRESH_TOKEN)} 字符")
print(f"  RT 前50:  {REFRESH_TOKEN[:50]}...")
print(f"  RT 后50:  ...{REFRESH_TOKEN[-50:]}")

import requests

try:
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": REFRESH_TOKEN,
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=30,
    )
    print(f"\n  HTTP 状态码: {resp.status_code}")
    print(f"  响应头 Content-Type: {resp.headers.get('Content-Type', 'N/A')}")

    try:
        body = resp.json()
        print(f"  响应 JSON:")
        print(f"    {json.dumps(body, indent=2, ensure_ascii=False)}")
    except Exception:
        print(f"  响应文本: {resp.text[:500]}")

    if resp.status_code == 200:
        access_token = body.get("access_token", "")
        new_rt = body.get("refresh_token", "")
        ok(f"Token 刷新成功")
        ok(f"Access Token 长度: {len(access_token)}")
        ok(f"新 Refresh Token: {'有 (' + str(len(new_rt)) + '字符)' if new_rt else '无'}")
        ok(f"Token 类型: {body.get('token_type', 'N/A')}")
        ok(f"过期时间: {body.get('expires_in', 'N/A')} 秒")
        ok(f"Scope: {body.get('scope', 'N/A')}")
    else:
        fail(f"Token 刷新失败 (HTTP {resp.status_code})")
        error_code = body.get("error", "N/A")
        error_desc = body.get("error_description", "N/A")
        error_codes = body.get("error_codes", [])
        info(f"error: {error_code}")
        info(f"error_codes: {error_codes}")
        # 截取关键错误描述
        if len(error_desc) > 300:
            info(f"error_description (前300字): {error_desc[:300]}")
        else:
            info(f"error_description: {error_desc}")

        # AADSTS 错误码解读
        if "9002313" in str(error_codes):
            info("→ AADSTS9002313: 请求格式错误或无效")
        elif "700016" in str(error_codes):
            info("→ AADSTS700016: client_id 不存在于 tenant 中")
        elif "70008" in str(error_codes):
            info("→ AADSTS70008: refresh_token 已过期")
        elif "700082" in str(error_codes):
            info("→ AADSTS700082: refresh_token 已撤销")
        elif "50020" in str(error_codes):
            info("→ AADSTS50020: 用户账号已禁用")
        elif "70000" in str(error_codes):
            info("→ AADSTS70000: 授权类型无效")
        elif "65001" in str(error_codes):
            info("→ AADSTS65001: 用户未同意请求的权限")
        else:
            info(f"→ 未识别的 AADSTS 错误码: {error_codes}")

    access_token = resp.json().get("access_token") if resp.status_code == 200 else None
except Exception as e:
    fail(f"请求异常: {e}")
    traceback.print_exc()
    access_token = None

# ============================================================
if access_token:
    section("第 2 步: Graph API 获取邮件 — 原始 HTTP 请求")
    # ============================================================
    try:
        resp2 = requests.get(
            "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"$top": "3", "$select": "id,subject,from,receivedDateTime"},
            timeout=30,
        )
        print(f"  HTTP 状态码: {resp2.status_code}")
        try:
            body2 = resp2.json()
            print(f"  响应 JSON (前1000字):")
            print(f"    {json.dumps(body2, indent=2, ensure_ascii=False)[:1000]}")
        except Exception:
            print(f"  响应文本: {resp2.text[:500]}")

        if resp2.status_code == 200:
            emails = body2.get("value", [])
            ok(f"获取到 {len(emails)} 封邮件")
            for e in emails:
                print(f"    - {e.get('subject', 'N/A')} | {e.get('receivedDateTime', 'N/A')}")
        elif resp2.status_code == 401:
            fail("401 Unauthorized — access_token 被拒绝")
            try:
                err = resp2.json()
                info(f"error code: {err.get('error', {}).get('code', 'N/A')}")
                info(f"error message: {err.get('error', {}).get('message', 'N/A')}")
            except Exception:
                pass
        else:
            fail(f"HTTP {resp2.status_code}")
    except Exception as e:
        fail(f"请求异常: {e}")
        traceback.print_exc()

    # ============================================================
    section("第 2b 步: Graph API 获取用户信息 — 验证 token 权限")
    # ============================================================
    try:
        resp2b = requests.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
        print(f"  HTTP 状态码: {resp2b.status_code}")
        try:
            body2b = resp2b.json()
            print(f"  响应:")
            print(f"    {json.dumps(body2b, indent=2, ensure_ascii=False)}")
        except Exception:
            print(f"  响应文本: {resp2b.text[:500]}")
        if resp2b.status_code == 200:
            ok(f"用户: {body2b.get('displayName', 'N/A')} ({body2b.get('mail', 'N/A')})")
    except Exception as e:
        fail(f"请求异常: {e}")

# ============================================================
section("第 3 步: IMAP OAuth2 登录测试 — outlook.live.com")
# ============================================================
try:
    import imaplib
    import base64

    if not access_token:
        info("跳过: 无可用 access_token")
    else:
        print(f"  连接 imap.live.com:993 ...")
        try:
            imap = imaplib.IMAP4_SSL("imap.live.com", 993)
            ok("SSL 连接成功")

            # OAuth2 认证 (XOAUTH2)
            auth_string = f"user={EMAIL}\x01auth=Bearer {access_token}\x01\x01"
            imap.authenticate("XOAUTH2", lambda x: auth_string.encode("utf-8"))
            ok("XOAUTH2 认证成功")

            status, data = imap.select("INBOX")
            ok(f"选择 INBOX: {status} ({data})")

            status, data = imap.search(None, "ALL")
            msg_count = len(data[0].split()) if data[0] else 0
            ok(f"邮件总数: {msg_count}")

            if msg_count > 0:
                status, data = imap.fetch(data[0].split()[-1], "(BODY[HEADER.FIELDS (SUBJECT FROM DATE)])")
                if data and data[0]:
                    print(f"  最新邮件头:")
                    print(f"    {data[0][1].decode(errors='replace')[:300]}")

            imap.logout()
            ok("登出成功")
        except imaplib.IMAP4.error as e:
            fail(f"IMAP 错误: {e}")
            # 尝试普通 LOGIN
            print(f"\n  尝试普通 LOGIN ...")
            try:
                imap2 = imaplib.IMAP4_SSL("imap.live.com", 993)
                imap2.login(EMAIL, PASSWORD)
                ok("普通 LOGIN 成功")
                imap2.logout()
            except Exception as e2:
                fail(f"普通 LOGIN 也失败: {e2}")
        except Exception as e:
            fail(f"连接异常: {type(e).__name__}: {e}")
except Exception as e:
    fail(f"IMAP 测试异常: {e}")
    traceback.print_exc()

# ============================================================
section("第 4 步: IMAP OAuth2 登录测试 — outlook.office365.com")
# ============================================================
try:
    import imaplib

    if not access_token:
        info("跳过: 无可用 access_token")
    else:
        print(f"  连接 outlook.office365.com:993 ...")
        try:
            imap = imaplib.IMAP4_SSL("outlook.office365.com", 993)
            ok("SSL 连接成功")

            auth_string = f"user={EMAIL}\x01auth=Bearer {access_token}\x01\x01"
            imap.authenticate("XOAUTH2", lambda x: auth_string.encode("utf-8"))
            ok("XOAUTH2 认证成功")

            status, data = imap.select("INBOX")
            ok(f"选择 INBOX: {status} ({data})")

            status, data = imap.search(None, "ALL")
            msg_count = len(data[0].split()) if data[0] else 0
            ok(f"邮件总数: {msg_count}")

            imap.logout()
            ok("登出成功")
        except imaplib.IMAP4.error as e:
            fail(f"IMAP 错误: {e}")
        except Exception as e:
            fail(f"连接异常: {type(e).__name__}: {e}")
except Exception as e:
    fail(f"IMAP 测试异常: {e}")
    traceback.print_exc()

# ============================================================
section("第 5 步: 检查数据库中存储的账号凭据")
# ============================================================
try:
    import sqlite3

    db_path = "data/outlook_accounts.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT email, client_id, refresh_token, account_type, status FROM accounts WHERE email = ?", (EMAIL,)).fetchone()

    if row:
        ok(f"找到账号记录")
        print(f"  email:       {row['email']}")
        print(f"  client_id:   {row['client_id']}")
        print(f"  account_type:{row['account_type']}")
        print(f"  status:      {row['status']}")
        stored_rt = row['refresh_token'] or ""
        print(f"  refresh_token 长度: {len(stored_rt)}")
        print(f"  refresh_token 前50:  {stored_rt[:50]}")
        if stored_rt.startswith("enc:"):
            ok("refresh_token 已加密存储")
            try:
                # 解密看看
                from dotenv import load_dotenv
                load_dotenv()
                from outlook_web.security.crypto import decrypt_data
                decrypted = decrypt_data(stored_rt)
                print(f"  解密后长度: {len(decrypted)}")
                print(f"  解密后前50: {decrypted[:50]}")
                if decrypted == REFRESH_TOKEN:
                    ok("解密后与提供的 RT 一致")
                else:
                    fail("解密后与提供的 RT 不一致!")
                    print(f"  解密后后50: ...{decrypted[-50:]}")
                    print(f"  提供的  后50: ...{REFRESH_TOKEN[-50:]}")
            except Exception as e:
                fail(f"解密失败: {e}")
        else:
            info("refresh_token 未加密 (明文)")
    else:
        info(f"数据库中未找到 {EMAIL} 的记录")
        # 列出所有账号
        rows = conn.execute("SELECT email, account_type, status, length(refresh_token) as rt_len FROM accounts").fetchall()
        info(f"数据库中共有 {len(rows)} 个账号:")
        for r in rows:
            print(f"    {r['email']} | type={r['account_type']} | status={r['status']} | rt_len={r['rt_len']}")
    conn.close()
except Exception as e:
    fail(f"数据库查询异常: {e}")
    traceback.print_exc()

print(f"\n{'='*60}")
print("  诊断完成")
print(f"{'='*60}")
