#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
扫码登录获取 refresh_token

使用方法:
    uv run --with qrcode --with pillow python scripts/qrcode_login.py
"""

import io
import json
import requests
import time
import sys
from pathlib import Path

try:
    import qrcode
    from PIL import Image
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

sys.path.insert(0, str(Path(__file__).parent.parent))


def generate_qr_image(url: str) -> io.BytesIO:
    """生成二维码图片"""
    if not HAS_QRCODE:
        return None

    qr = qrcode.QRCode(version=2, box_size=2, border=1)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image().convert('RGB')

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf


def push_qr_to_feishu(qrcode_key: str, qrcode_url: str):
    """推送二维码到飞书"""
    try:
        from app.modules.push_channels.feishu import upload_image_to_feishu, get_feishu_tenant_access_token
        import requests

        # 生成二维码图片
        buf = generate_qr_image(qrcode_url)
        if not buf:
            print("无法生成二维码图片")
            return False

        # 保存到临时文件
        temp_file = Path("/tmp/bilibili_qrcode.png")
        with open(temp_file, 'wb') as f:
            f.write(buf.getvalue())

        # 上传图片到飞书
        image_key = upload_image_to_feishu(str(temp_file))
        if not image_key:
            print("飞书图片上传失败")
            return False

        # 发送图片消息
        token = get_feishu_tenant_access_token()
        if not token:
            print("获取飞书token失败")
            return False

        from config import Config
        receive_id = Config.FEISHU_RECEIVE_ID
        receive_id_type = Config.FEISHU_RECEIVE_ID_TYPE

        url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={receive_id_type}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }

        payload = {
            "receive_id": receive_id,
            "msg_type": "image",
            "content": json.dumps({"image_key": image_key})
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        result = resp.json()

        if result.get("code") == 0:
            # 发送文字提示
            text_url = f"https://account.bilibili.com/h5/account-h5/auth/scan-web?qrcode_key={qrcode_key}"
            text_payload = {
                "receive_id": receive_id,
                "msg_type": "text",
                "content": json.dumps({
                    "text": f"请用 B站 App 扫码登录（不要截图！点击图片放大后直接扫描）\n\n或者复制链接到浏览器扫码:\n{text_url}"
                })
            }
            requests.post(url, headers=headers, json=text_payload, timeout=15)

            print("✓ 飞书推送成功")
            return True
        else:
            print(f"飞书推送失败: {result.get('msg')}")
            return False
    except Exception as e:
        print(f"飞书推送异常: {e}")
        return False


def push_qr_to_telegram(qrcode_key: str, qrcode_url: str):
    """推送二维码到 Telegram"""
    try:
        import telegram
        from config import Config

        if not Config.TELEGRAM_TOKEN or not Config.TELEGRAM_CHAT_ID:
            print("Telegram 未配置")
            return False

        bot = telegram.Bot(token=Config.TELEGRAM_TOKEN)

        # 生成二维码图片
        buf = generate_qr_image(qrcode_url)
        if not buf:
            print("无法生成二维码图片")
            return False

        # 保存到临时文件
        temp_file = Path("/tmp/bilibili_qrcode.png")
        with open(temp_file, 'wb') as f:
            f.write(buf.getvalue())

        # 发送图片
        with open(temp_file, 'rb') as f:
            bot.send_photo(chat_id=Config.TELEGRAM_CHAT_ID, photo=f,
                          caption=f"请使用 B站 App 扫码登录\n二维码key: {qrcode_key}")

        print("✓ Telegram推送成功")
        return True
    except Exception as e:
        print(f"Telegram推送异常: {e}")
        return False


def qrcode_login():
    """扫码登录获取 refresh_token"""

    # 1. 申请二维码
    url = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
        "Referer": "https://www.bilibili.com/",
    }
    resp = requests.get(url, headers=headers)

    if resp.status_code != 200:
        print(f"申请二维码失败: HTTP {resp.status_code}")
        return None

    data = resp.json()
    if data["code"] != 0:
        print(f"申请二维码失败: {data}")
        return None

    qrcode_key = data["data"]["qrcode_key"]
    # 直接用 qrcode_key 构建简洁的扫码链接
    qrcode_url = f"https://account.bilibili.com/h5/account-h5/auth/scan-web?qrcode_key={qrcode_key}"

    print("=" * 60)
    print("正在推送二维码到各渠道...")
    print("=" * 60)

    # 推送到各渠道
    pushed = []
    if push_qr_to_feishu(qrcode_key, qrcode_url):
        pushed.append("飞书")
        print("✓ 已推送到飞书")
    if push_qr_to_telegram(qrcode_key, qrcode_url):
        pushed.append("Telegram")
        print("✓ 已推送到Telegram")

    if not pushed:
        print("未成功推送到任何渠道，将显示二维码链接供手动扫描")

    print(f"\nqrcode_key: {qrcode_key}")
    print("请使用 B站 App 扫码登录")
    print("=" * 60)

    # 2. 轮询扫码状态
    poll_url = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
    poll_params = {"qrcode_key": qrcode_key}

    for i in range(180):
        resp = requests.get(poll_url, params=poll_params, headers=headers)

        if resp.status_code != 200:
            print(f"轮询请求失败: HTTP {resp.status_code}")
            time.sleep(2)
            continue

        try:
            result = resp.json()
        except Exception:
            print(f"JSON解析失败: body={resp.text[:200]}")
            time.sleep(2)
            continue

        # 登录成功的判断：顶层 code == 0 且 data 中有 refresh_token
        top_code = result.get("code")
        data = result.get("data", {})
        refresh_token = data.get("refresh_token", "") if isinstance(data, dict) else ""

        if top_code == 0 and refresh_token:
            print(f"\n登录成功!")
            print(f"refresh_token: {refresh_token[:50]}...")

            # 从响应头中提取 Cookie
            cookies = resp.cookies
            cookie_dict = {}
            # resp.cookies is a RequestsCookieJar which is dict-like
            for key in cookies.keys():
                cookie_dict[key] = cookies.get(key)

            # 也从 data 中获取 cookie（如果B站返回了）
            if isinstance(data, dict) and data.get("cookie"):
                resp_cookie = data.get("cookie")
                for item in resp_cookie.split(";"):
                    item = item.strip()
                    if "=" in item:
                        k, v = item.split("=", 1)
                        cookie_dict[k.strip()] = v.strip()

            # 构建完整的 Cookie 字符串
            if cookie_dict:
                full_cookie = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])
                print(f"获取到新 Cookie: {list(cookie_dict.keys())}")
                return refresh_token, full_cookie
            else:
                return refresh_token, None

        # 打印原始响应以便调试
        if i < 3:
            print(f"[调试] resp={resp.text[:300]}")

        # 根据状态码处理（有些响应把 code 放在 data 里）
        code = top_code if top_code is not None else (data.get("code") if isinstance(data, dict) else None)
        msg = result.get("message", data.get("message", "") if isinstance(data, dict) else "")

        if code == 86101:
            if i % 10 == 0:
                print("等待扫码...")
        elif code == 86090:
            print("已扫码，请确认登录...")
        elif code == 86038:
            print("二维码过期，重新生成...")
            return None
        else:
            print(f"状态码: {code}, 消息: {msg}")

        time.sleep(2)

    return None


def save_to_env(refresh_token: str, cookie: str = None) -> bool:
    """保存 refresh_token 和 cookie 到 .env"""
    try:
        env_file = Path(__file__).parent.parent / ".env"

        # 读取现有配置
        env_lines = []
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                env_lines = f.readlines()

        # 更新 refresh_token
        found_refresh = False
        found_cookie = False
        for i, line in enumerate(env_lines):
            if line.startswith("refresh_token="):
                env_lines[i] = f'refresh_token="{refresh_token}"\n'
                found_refresh = True
            elif line.startswith("BILIBILI_COOKIE=") and cookie:
                env_lines[i] = f'BILIBILI_COOKIE="{cookie}"\n'
                found_cookie = True

        if not found_refresh:
            env_lines.append(f'refresh_token="{refresh_token}"\n')
        if not found_cookie and cookie:
            env_lines.append(f'BILIBILI_COOKIE="{cookie}"\n')

        with open(env_file, "w", encoding="utf-8") as f:
            f.writelines(env_lines)

        print(f"\nrefresh_token 已保存到 .env")
        if cookie:
            print(f"BILIBILI_COOKIE 已保存到 .env")
        return True
    except Exception as e:
        print(f"保存失败: {e}")
        return False


if __name__ == "__main__":
    print("B站扫码登录 - 获取 refresh_token 和 Cookie")
    print("=" * 60)

    result = qrcode_login()

    if result:
        refresh_token, cookie = result if isinstance(result, tuple) else (result, None)
        save_to_env(refresh_token, cookie)
        print("\n完成！现在可以重启程序了。")
    else:
        print("\n获取失败，请重试。")
        sys.exit(1)