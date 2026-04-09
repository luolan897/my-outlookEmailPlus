"""
完整端到端测试：模拟导入 → 验证存储 → 获取邮件
直接调用 controller/repo 层，不走 HTTP
"""
import json
import sys
import traceback

# ============================================================
# 用户提供的凭据（单行版本）
# ============================================================
ACCOUNT_STR = (
    "onvoam11571l@hotmail.com----ni473830----9e5f94bc-e8a4-4e73-b8be-63364c29d753"
    "----M.C559_SN1.0.U.CnlQlHCseit2zzQYcLU5jIWbRRwseUYhMT2Tr75w2WaYiMLnXPNg4v6ddst8op*wijEP"
    "bC4LcfAHAJErq6vXTKPi3qybdldarJVEgkvuixon9q3aYfW9sxVZ2HBcsNUspP3DZpLuLuHFWVqgjsTHTBLUfn674jR!"
    "2Z3d7DWuz90MpnmhBqieDUh6jo0GRFlW9F8GBaOJm0H6sMff1Z3YDO!DeT8ynVgQkGdlEkN*"
    "z4Jo94dEJbyaaMSyhkQD0WUHHvrPFCXku!tZhxfi!jOooeH2gHE2IOmQS8NDI0s6nsuRY7SibuzIpswYA*"
    "GymV5ZcqLu63uKRbHm2pfiR2ddvXXl1TnfTfOnIwhdJ!1ie1iSYAiEFANKn9U7bGEd!u1bsncE0ceBX60nzeCCz8x6QMA$"
)


def ok(msg):
    print(f"  [OK]   {msg}")


def fail(msg, detail=""):
    print(f"  [FAIL] {msg}")
    if detail:
        print(f"         {detail}")


def info(msg):
    print(f"  [INFO] {msg}")


# ============================================================
# 1. 模拟导入流程（复制 controller 中的合并+解析逻辑）
# ============================================================
print("=" * 60)
print("  第 1 步：模拟导入解析")
print("=" * 60)

raw_lines = ACCOUNT_STR.splitlines()
print(f"  splitlines() 结果: {len(raw_lines)} 行")
for i, l in enumerate(raw_lines):
    print(f"    行{i+1}: {l[:80]}...")

# 合并续行
merged_lines = []
for _line in raw_lines:
    _stripped = _line.strip()
    if not _stripped:
        continue
    if merged_lines and "----" not in _stripped and not _stripped.startswith("#"):
        merged_lines[-1] += _stripped
    else:
        merged_lines.append(_stripped)
raw_lines = merged_lines
print(f"  合并后: {len(raw_lines)} 行")

# 解析
parts = raw_lines[0].split("----")
print(f"  split('----') 段数: {len(parts)}")
email = parts[0].strip()
password = parts[1]
client_id = parts[2].strip()
refresh_token = "----".join(parts[3:])
print(f"  email:         {email}")
print(f"  password:      {password}")
print(f"  client_id:     {client_id}")
print(f"  RT 长度:       {len(refresh_token)} 字符")
print(f"  RT 前50:       {refresh_token[:50]}")
print(f"  RT 后50:       ...{refresh_token[-50:]}")

if len(parts) >= 4:
    ok("解析成功，4 段格式正确")
else:
    fail(f"段数不对: {len(parts)}")
    sys.exit(1)

# ============================================================
# 2. 测试 Refresh Token 有效性
# ============================================================
print(f"\n{'='*60}")
print("  第 2 步：测试 Refresh Token 有效性")
print("=" * 60)

import requests

try:
    resp = requests.post(
        "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        data={
            "client_id": client_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=30,
    )
    print(f"  HTTP 状态码: {resp.status_code}")

    if resp.status_code == 200:
        body = resp.json()
        access_token = body.get("access_token", "")
        new_rt = body.get("refresh_token", "")
        ok(f"Token 刷新成功")
        ok(f"Access Token 长度: {len(access_token)}")
        ok(f"Scope: {body.get('scope', 'N/A')}")
        if new_rt:
            info(f"返回了新 RT ({len(new_rt)} 字符)")
        else:
            info("未返回新 RT（正常，非所有刷新都返回）")
    else:
        body = resp.json()
        fail(f"Token 刷新失败")
        error_codes = body.get("error_codes", [])
        error_desc = body.get("error_description", "")
        info(f"error: {body.get('error')}")
        info(f"error_codes: {error_codes}")
        info(f"error_description (前200字): {error_desc[:200]}")
        sys.exit(1)
except Exception as e:
    fail(f"请求异常: {e}")
    traceback.print_exc()
    sys.exit(1)

# ============================================================
# 3. 测试 Graph API 获取邮件
# ============================================================
print(f"\n{'='*60}")
print("  第 3 步：Graph API 获取邮件")
print("=" * 60)

try:
    resp2 = requests.get(
        "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"$top": "3", "$select": "id,subject,from,receivedDateTime,bodyPreview"},
        timeout=30,
    )
    print(f"  HTTP 状态码: {resp2.status_code}")

    if resp2.status_code == 200:
        body2 = resp2.json()
        emails = body2.get("value", [])
        ok(f"Graph API 成功，获取到 {len(emails)} 封邮件")
        for e in emails:
            sender = e.get("from", {}).get("emailAddress", {}).get("address", "N/A")
            print(f"    - {e.get('subject', 'N/A')}")
            print(f"      来自: {sender}")
            print(f"      时间: {e.get('receivedDateTime', 'N/A')}")
        if not emails:
            info("收件箱为空")
    else:
        try:
            err = resp2.json()
            info(f"Graph API 错误: {json.dumps(err, ensure_ascii=False)[:300]}")
        except Exception:
            info(f"Graph API 响应: {resp2.text[:300]}")

        # 401 时测试 IMAP 回退
        if resp2.status_code == 401:
            info("Graph API 返回 401，将测试 IMAP 回退")
except Exception as e:
    fail(f"Graph API 请求异常: {e}")

# ============================================================
# 4. 测试 IMAP OAuth2 (outlook.office365.com)
# ============================================================
print(f"\n{'='*60}")
print("  第 4 步：IMAP OAuth2 (outlook.office365.com)")
print("=" * 60)

try:
    import imaplib

    imap = imaplib.IMAP4_SSL("outlook.office365.com", 993)
    ok("SSL 连接成功")

    auth_string = f"user={email}\x01auth=Bearer {access_token}\x01\x01"
    imap.authenticate("XOAUTH2", lambda x: auth_string.encode("utf-8"))
    ok("XOAUTH2 认证成功")

    status, data = imap.select("INBOX")
    ok(f"选择 INBOX: {status} ({data[0].decode() if data else ''})")

    status, data = imap.search(None, "ALL")
    msg_ids = data[0].split() if data[0] else []
    ok(f"邮件总数: {len(msg_ids)}")

    if msg_ids:
        # 获取最新 3 封的 SUBJECT
        for mid in msg_ids[-3:]:
            status, data = imap.fetch(mid, "(BODY[HEADER.FIELDS (SUBJECT FROM DATE)])")
            if data and data[0]:
                header = data[0][1].decode(errors="replace").strip()
                print(f"    {header[:120]}")

    imap.logout()
    ok("登出成功")
except imaplib.IMAP4.error as e:
    fail(f"IMAP 错误: {e}")
except Exception as e:
    fail(f"IMAP 异常: {type(e).__name__}: {e}")

# ============================================================
# 5. 模拟存入数据库 → 再读出验证完整性
# ============================================================
print(f"\n{'='*60}")
print("  第 5 步：数据库加密存储 → 读取验证")
print("=" * 60)

try:
    from dotenv import load_dotenv
    load_dotenv()
    from outlook_web.security.crypto import encrypt_data, decrypt_data

    enc_rt = encrypt_data(refresh_token)
    print(f"  加密后长度: {len(enc_rt)}")
    ok("加密成功")

    dec_rt = decrypt_data(enc_rt)
    print(f"  解密后长度: {len(dec_rt)}")

    if dec_rt == refresh_token:
        ok("解密后 RT 与原始完全一致")
    else:
        fail("解密后 RT 与原始不一致!")
        print(f"  原始长度: {len(refresh_token)}")
        print(f"  解密长度: {len(dec_rt)}")
        # 找差异位置
        for i in range(min(len(refresh_token), len(dec_rt))):
            if refresh_token[i] != dec_rt[i]:
                print(f"  首个差异位置: {i}")
                print(f"  原始: ...{refresh_token[max(0,i-5):i+20]}...")
                print(f"  解密: ...{dec_rt[max(0,i-5):i+20]}...")
                break
except Exception as e:
    fail(f"加解密测试异常: {e}")
    traceback.print_exc()

# ============================================================
# 6. 模拟完整 Flask 应用导入流程
# ============================================================
print(f"\n{'='*60}")
print("  第 6 步：Flask 应用内完整导入测试")
print("=" * 60)

try:
    from tests._import_app import clear_login_attempts, import_web_app_module

    module = import_web_app_module()
    app = module.app

    with app.app_context():
        clear_login_attempts()

        # 清理旧数据
        conn = module.create_sqlite_connection()
        try:
            conn.execute("DELETE FROM accounts WHERE email = ?", (email,))
            conn.commit()
        finally:
            conn.close()
        ok("清理旧数据完成")

        # 通过 repo 层直接导入
        from outlook_web.security.crypto import encrypt_data
        enc_pw = encrypt_data(password)

        result = module.add_account(
            email, enc_pw, client_id, refresh_token,
            group_id=1, account_type="outlook", provider="outlook",
        )
        # add_account 返回的是 accounts_repo.add_account 的结果
        # 但 web_outlook_app 没有直接暴露 add_account，需要直接用 repo
        from outlook_web.repositories import accounts as accounts_repo

        # 先删除再添加
        conn = module.create_sqlite_connection()
        try:
            conn.execute("DELETE FROM accounts WHERE email = ?", (email,))
            conn.commit()
        finally:
            conn.close()

        ok_ref = accounts_repo.add_account(
            email, password, client_id, refresh_token,
            group_id=1, account_type="outlook", provider="outlook",
        )
        if ok_ref:
            ok("repo.add_account 写入成功")

            # 读回验证
            account = accounts_repo.get_account_by_email(email)
            if account:
                stored_rt_enc = account.get("refresh_token", "")
                stored_rt = account.get("_decrypted_refresh_token", "")
                # load_accounts 会自动解密，但 get_account_by_email 不会
                # 直接解密
                from outlook_web.security.crypto import decrypt_data
                if stored_rt_enc:
                    stored_rt_dec = decrypt_data(stored_rt_enc)
                else:
                    stored_rt_dec = stored_rt_enc

                ok(f"读回 RT 长度: {len(stored_rt_dec)}")
                if stored_rt_dec == refresh_token:
                    ok("数据库中 RT 与原始完全一致")
                else:
                    fail("数据库中 RT 不一致!")
                    print(f"  数据库: {stored_rt_dec[:80]}...")
                    print(f"  原始:   {refresh_token[:80]}...")
            else:
                fail("读回账号失败")
        else:
            fail("repo.add_account 写入失败")

        # 清理
        conn = module.create_sqlite_connection()
        try:
            conn.execute("DELETE FROM accounts WHERE email = ?", (email,))
            conn.commit()
        finally:
            conn.close()
        ok("清理完成")

except Exception as e:
    fail(f"Flask 导入测试异常: {e}")
    traceback.print_exc()

print(f"\n{'='*60}")
print("  全部测试完成")
print(f"{'='*60}")
