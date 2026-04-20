#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站扫码登录命令

使用方法:
    uv run python -m app.cli login
    uv run bili-login
"""

import io
import json
import sys
import requests
import time
from pathlib import Path
import typer

cli = typer.Typer(help="B站自动化工具")

# 尝试导入 qrcode
try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False


def generate_qr_image(url: str) -> io.BytesIO | None:
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


def push_qr_to_feishu(qrcode_key: str, qrcode_url: str) -> bool:
    """推送二维码到飞书"""
    try:
        # 确保项目路径已添加
        project_root = Path(__file__).parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from app.modules.push_channels.feishu import upload_image_to_feishu, get_feishu_tenant_access_token

        buf = generate_qr_image(qrcode_url)
        if not buf:
            typer.echo("无法生成二维码图片")
            return False

        temp_file = Path("/tmp/bilibili_qrcode.png")
        with open(temp_file, 'wb') as f:
            f.write(buf.getvalue())

        image_key = upload_image_to_feishu(str(temp_file))
        if not image_key:
            typer.echo("飞书图片上传失败")
            return False

        token = get_feishu_tenant_access_token()
        if not token:
            typer.echo("获取飞书token失败")
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
                    "text": f"请用 B站 App 扫码登录（点击图片放大后直接扫描）\n\n或者复制链接到浏览器扫码:\n{text_url}"
                })
            }
            requests.post(url, headers=headers, json=text_payload, timeout=15)
            return True
        else:
            typer.echo(f"飞书推送失败: {result.get('msg')}")
            return False
    except Exception as e:
        typer.echo(f"飞书推送异常: {e}")
        return False


def push_qr_to_telegram(qrcode_key: str, qrcode_url: str) -> bool:
    """推送二维码到 Telegram"""
    try:
        # 确保项目路径已添加
        project_root = Path(__file__).parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        import telegram
        from config import Config

        if not Config.TELEGRAM_TOKEN or not Config.TELEGRAM_CHAT_ID:
            return False

        bot = telegram.Bot(token=Config.TELEGRAM_TOKEN)

        buf = generate_qr_image(qrcode_url)
        if not buf:
            return False

        temp_file = Path("/tmp/bilibili_qrcode.png")
        with open(temp_file, 'wb') as f:
            f.write(buf.getvalue())

        with open(temp_file, 'rb') as f:
            bot.send_photo(chat_id=Config.TELEGRAM_CHAT_ID, photo=f,
                          caption=f"请使用 B站 App 扫码登录\n二维码key: {qrcode_key}")
        return True
    except Exception as e:
        typer.echo(f"Telegram推送异常: {e}")
        return False


def save_to_env(refresh_token: str, cookie: str = None) -> bool:
    """保存 refresh_token 和 cookie 到 .env"""
    try:
        # 找项目根目录的 .env
        env_file = Path(__file__).parent.parent.parent / ".env"
        # 或从当前工作目录
        if not env_file.exists():
            env_file = Path.cwd() / ".env"

        env_lines = []
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                env_lines = f.readlines()

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

        return True
    except Exception as e:
        typer.echo(f"保存失败: {e}")
        return False


@cli.command()
def login():
    """
    扫码登录 B站，获取 refresh_token 和 Cookie

    二维码会推送到已配置的飞书/Telegram频道，
    也可以直接查看终端中的二维码链接。
    """
    typer.echo("B站扫码登录 - 获取 refresh_token 和 Cookie")
    typer.echo("=" * 60)

    # 1. 申请二维码
    url = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
        "Referer": "https://www.bilibili.com/",
    }
    resp = requests.get(url, headers=headers)

    if resp.status_code != 200:
        typer.echo(f"申请二维码失败: HTTP {resp.status_code}")
        raise typer.Exit(1)

    data = resp.json()
    if data["code"] != 0:
        typer.echo(f"申请二维码失败: {data}")
        raise typer.Exit(1)

    qrcode_key = data["data"]["qrcode_key"]
    qrcode_url = f"https://account.bilibili.com/h5/account-h5/auth/scan-web?qrcode_key={qrcode_key}"

    typer.echo("正在推送二维码到各渠道...")
    typer.echo("=" * 60)

    pushed = []
    if push_qr_to_feishu(qrcode_key, qrcode_url):
        pushed.append("飞书")
        typer.echo("✓ 已推送到飞书")
    if push_qr_to_telegram(qrcode_key, qrcode_url):
        pushed.append("Telegram")
        typer.echo("✓ 已推送到Telegram")

    if not pushed:
        typer.echo("未推送到任何渠道，将显示二维码链接")

    typer.echo(f"\nqrcode_key: {qrcode_key}")
    typer.echo(f"二维码链接: {qrcode_url}")
    typer.echo("请使用 B站 App 扫码登录")
    typer.echo("=" * 60)

    # 2. 轮询扫码状态
    poll_url = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
    poll_params = {"qrcode_key": qrcode_key}

    for i in range(180):
        resp = requests.get(poll_url, params=poll_params, headers=headers)

        if resp.status_code != 200:
            time.sleep(2)
            continue

        try:
            result = resp.json()
        except Exception:
            time.sleep(2)
            continue

        top_code = result.get("code")
        data = result.get("data", {})
        refresh_token = data.get("refresh_token", "") if isinstance(data, dict) else ""

        if top_code == 0 and refresh_token:
            typer.echo("\n✓ 登录成功!")
            typer.echo(f"refresh_token: {refresh_token[:50]}...")

            # 获取 Cookie
            cookies = resp.cookies
            cookie_dict = {}
            for key in cookies.keys():
                cookie_dict[key] = cookies.get(key)

            if isinstance(data, dict) and data.get("cookie"):
                resp_cookie = data.get("cookie")
                for item in resp_cookie.split(";"):
                    item = item.strip()
                    if "=" in item:
                        k, v = item.split("=", 1)
                        cookie_dict[k.strip()] = v.strip()

            if cookie_dict:
                full_cookie = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])
                typer.echo(f"获取到新 Cookie: {list(cookie_dict.keys())}")
                save_to_env(refresh_token, full_cookie)
            else:
                save_to_env(refresh_token)

            typer.echo("\n完成！refresh_token 和 Cookie 已保存到 .env")
            typer.echo("现在可以重启程序了。")
            raise typer.Exit(0)

        data_code = data.get("code") if isinstance(data, dict) else None
        data_msg = data.get("message", "") if isinstance(data, dict) else ""
        code = top_code if top_code is not None else data_code
        msg = data_msg or result.get("message", "")

        if code == 86101:
            if i % 10 == 0:
                typer.echo("等待扫码...")
        elif code == 86090:
            typer.echo("已扫码，请确认登录...")
        elif code == 86038:
            typer.echo("二维码过期，请重新生成...")
            raise typer.Exit(1)
        elif code != 0:
            typer.echo(f"状态码: {code}, 消息: {msg}")

        time.sleep(2)

    typer.echo("\n超时，扫码失败")
    raise typer.Exit(1)


if __name__ == "__main__":
    cli()