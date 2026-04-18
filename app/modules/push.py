import json
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional
from app.utils.logger import get_logger
from config import Config

logger = get_logger("push")

# 飞书 tenant_access_token 缓存
_feishu_token_cache = None
_feishu_token_expire_at = 0


def upload_image_to_feishu(image_path: str) -> Optional[str]:
    """
    上传图片到飞书并返回 image_key

    Args:
        image_path: 图片本地路径

    Returns:
        image_key 成功，None 失败
    """
    token = get_feishu_tenant_access_token()
    if not token:
        return None

    url = "https://open.feishu.cn/open-apis/im/v1/images"
    headers = {
        "Authorization": f"Bearer {token}"
    }

    try:
        path = Path(image_path)
        if not path.exists():
            logger.warning("图片文件不存在: %s", image_path)
            return None

        files = {
            "image": (path.name, path.read_bytes(), "image/png")
        }
        data = {"image_type": "message"}

        resp = requests.post(url, headers=headers, data=data, files=files, timeout=30)
        result = resp.json()

        if result.get("code") == 0:
            image_key = result.get("data", {}).get("image_key", "")
            logger.debug("图片上传成功: %s -> %s", image_path, image_key)
            return image_key
        else:
            logger.error("图片上传失败: code=%s, msg=%s", result.get("code"), result.get("msg"))
            return None
    except Exception as e:
        logger.error("图片上传异常: %s", e)
        return None


def push_feishu_image(image_key: str) -> bool:
    """
    通过飞书应用推送图片消息

    Args:
        image_key: 飞书图片 key

    Returns:
        bool: 是否成功
    """
    token = get_feishu_tenant_access_token()
    if not token:
        return False

    url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={Config.FEISHU_RECEIVE_ID_TYPE}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }

    content_json = json.dumps({"image_key": image_key}, ensure_ascii=False)
    payload_dict = {
        "receive_id": Config.FEISHU_RECEIVE_ID,
        "msg_type": "image",
        "content": content_json
    }

    try:
        resp = requests.post(url, headers=headers, json=payload_dict, timeout=15)
        data = resp.json()

        if data.get("code") == 0:
            return True
        else:
            logger.error("飞书图片推送失败: code=%s, msg=%s", data.get("code"), data.get("msg"))
            return False
    except Exception as e:
        logger.error("飞书图片推送异常: %s", e)
        return False


def get_feishu_tenant_access_token() -> Optional[str]:
    """
    获取飞书 tenant_access_token（带缓存）

    Returns:
        str: access_token，失败返回 None
    """
    global _feishu_token_cache, _feishu_token_expire_at

    now = datetime.now().timestamp()

    # 如果 token 还在有效期内（提前5分钟过期），直接返回缓存
    if _feishu_token_cache and now < _feishu_token_expire_at - 300:
        return _feishu_token_cache

    if not Config.FEISHU_APP_ID or not Config.FEISHU_APP_SECRET:
        logger.warning("飞书 APP_ID 或 APP_SECRET 未配置")
        return None

    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    payload = {
        "app_id": Config.FEISHU_APP_ID,
        "app_secret": Config.FEISHU_APP_SECRET
    }

    try:
        resp = requests.post(url, json=payload, timeout=15)
        data = resp.json()

        if data.get("code") == 0:
            _feishu_token_cache = data["tenant_access_token"]
            _feishu_token_expire_at = now + data["expire"]
            logger.debug("飞书 tenant_access_token 获取成功")
            return _feishu_token_cache
        else:
            logger.error("飞书 tenant_access_token 获取失败: %s", data.get("msg"))
            return None
    except Exception as e:
        logger.error("飞书 tenant_access_token 请求异常: %s", e)
        return None


def push_feishu_text(content: str) -> bool:
    """
    推送纯文本消息到飞书（优先使用应用模式，回退到 webhook）

    Args:
        content: 文本内容

    Returns:
        bool: 是否成功
    """
    # 优先使用应用模式
    if Config.FEISHU_APP_ID and Config.FEISHU_APP_SECRET and Config.FEISHU_RECEIVE_ID:
        if push_feishu_text_by_app(content):
            return True

    # 回退到 webhook 模式
    if Config.FEISHU_WEBHOOK:
        return push_feishu_text_by_webhook(Config.FEISHU_WEBHOOK, content)

    logger.debug("飞书未配置，跳过推送")
    return False


def push_feishu_text_by_webhook(webhook_url: str, content: str) -> bool:
    """
    通过 webhook 推送纯文本消息到飞书

    Args:
        webhook_url: 飞书 webhook URL
        content: 文本内容

    Returns:
        bool: 是否成功
    """
    payload = {
        "msg_type": "text",
        "content": {"text": content}
    }
    resp = requests.post(webhook_url, json=payload, timeout=15)
    if resp.status_code == 200 and resp.json().get("StatusCode") in (0, 200):
        return True
    logger.error("飞书 webhook 推送失败: %s", resp.text)
    return False


def push_feishu_text_by_app(content: str) -> bool:
    """
    通过飞书应用推送纯文本消息

    Args:
        content: 文本内容

    Returns:
        bool: 是否成功
    """
    token = get_feishu_tenant_access_token()
    if not token:
        return False

    # receive_id_type 需要放在查询字符串中
    url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={Config.FEISHU_RECEIVE_ID_TYPE}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }

    content_json = json.dumps({"text": content}, ensure_ascii=False)
    payload_dict = {
        "receive_id": Config.FEISHU_RECEIVE_ID,
        "msg_type": "text",
        "content": content_json
    }

    try:
        resp = requests.post(url, headers=headers, json=payload_dict, timeout=15)
        data = resp.json()

        if data.get("code") == 0:
            logger.debug("飞书应用推送成功")
            return True
        else:
            logger.error("飞书应用推送失败: code=%s, msg=%s", data.get("code"), data.get("msg"))
            return False
    except Exception as e:
        logger.error("飞书应用推送异常: %s", e, exc_info=True)
        return False


def push_feishu_video(content_data: dict) -> bool:
    """
    推送视频到飞书

    Args:
        content_data: 视频内容数据

    Returns:
        bool: 是否成功
    """
    title = content_data.get("title", "无标题")
    summary = content_data.get("summary", "")
    url = content_data.get("url", "")
    tags = content_data.get("tags", [])
    stocks = content_data.get("stocks", [])
    doc_url = content_data.get("doc_url", "")

    text = f"📺 新视频\n\n{title}\n\n"
    if summary:
        text += f"{summary}\n\n"
    if stocks:
        text += f"📈 涉及股票: {'、'.join(stocks)}\n\n"
    if tags:
        text += f"标签: {' '.join([f'#{t}' for t in tags])}\n\n"
    text += f"🔗 原视频: {url}"
    if doc_url:
        text += f"\n📄 详细总结: {doc_url}"

    return push_feishu_text(text)


def push_feishu_dynamic(content_data: dict) -> bool:
    """
    推送动态到飞书

    Args:
        content_data: 动态内容数据

    Returns:
        bool: 是否成功
    """
    text = content_data.get("text", "")
    url = content_data.get("url", "")
    pub_time = content_data.get("pub_time", "")

    # 格式化时间为 年月日时分秒
    if pub_time:
        try:
            # pub_time 可能是 "2026-04-16 10:30:00" 格式
            dt = datetime.strptime(pub_time, "%Y-%m-%d %H:%M:%S")
            pub_time_str = dt.strftime("%Y年%m月%d日 %H:%M:%S")
        except (ValueError, TypeError):
            # 如果解析失败，保留原字符串
            pub_time_str = pub_time
    else:
        pub_time_str = ""

    # 截断过长的文本
    display_text = text[:500]
    if len(text) > 500:
        display_text += "..."

    msg = f"📝 新动态\n\n{display_text}\n\n"
    if pub_time_str:
        msg += f"⏰ {pub_time_str}\n"
    msg += f"🔗 {url}"

    # 先发送文本
    if not push_feishu_text(msg):
        return False

    # 发送图片（最多4张）
    images = content_data.get("images", []) or []
    for img_path in images[:4]:
        image_key = upload_image_to_feishu(img_path)
        if image_key:
            push_feishu_image(image_key)

    return True


def push_feishu_dynamic_card(content_data: dict) -> bool:
    """
    使用飞书卡片消息推送动态（支持内嵌图片）

    Args:
        content_data: 动态内容数据

    Returns:
        bool: 是否成功
    """
    token = get_feishu_tenant_access_token()
    if not token:
        logger.warning("无法获取飞书 token")
        return False

    text = content_data.get("text", "")
    url = content_data.get("url", "")
    pub_time = content_data.get("pub_time", "")
    images = content_data.get("images", []) or []

    # 格式化时间
    if pub_time:
        try:
            dt = datetime.strptime(pub_time, "%Y-%m-%d %H:%M:%S")
            pub_time_str = dt.strftime("%Y年%m月%d日 %H:%M:%S")
        except (ValueError, TypeError):
            pub_time_str = pub_time
    else:
        pub_time_str = ""

    # 截断文本
    display_text = text[:1000]
    if len(text) > 1000:
        display_text += "..."

    # 先上传所有图片获取 image_key
    image_keys = []
    for img_path in images[:4]:
        image_key = upload_image_to_feishu(img_path)
        if image_key:
            image_keys.append(image_key)

    # 构建卡片元素
    elements = []

    # 文本内容 - text 必须是对象格式
    elements.append({
        "tag": "div",
        "text": {
            "tag": "plain_text",
            "content": display_text
        }
    })

    # 添加图片
    for key in image_keys:
        elements.append({
            "tag": "img",
            "img_key": key
        })

    # 时间
    if pub_time_str:
        elements.append({
            "tag": "div",
            "text": {
                "tag": "plain_text",
                "content": f"⏰ {pub_time_str}"
            },
            "text_align": "left"
        })

    # 链接 - 使用 lark_md 标签的 markdown 链接格式
    if url:
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"[🔗 查看原动态]({url})"
            }
        })

    # 构建卡片
    card = {
        "config": {
            "wide_screen_mode": True
        },
        "header": {
            "title": {
                "tag": "plain_text",
                "text": "📝 新动态"
            },
            "template": "blue"
        },
        "elements": elements
    }

    # 发送卡片消息
    url_api = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={Config.FEISHU_RECEIVE_ID_TYPE}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }

    payload = {
        "receive_id": Config.FEISHU_RECEIVE_ID,
        "msg_type": "interactive",
        "content": json.dumps(card, ensure_ascii=False)
    }

    try:
        resp = requests.post(url_api, headers=headers, json=payload, timeout=30)
        data = resp.json()

        if data.get("code") == 0:
            logger.info("飞书卡片消息推送成功")
            return True
        else:
            logger.error("飞书卡片推送失败: code=%s, msg=%s", data.get("code"), data.get("msg"))
            return False
    except Exception as e:
        logger.error("飞书卡片推送异常: %s", e)
        return False


def push_telegram_dynamic(bot_token: str, chat_id: str, content_data: dict) -> bool:
    """占位符实现"""
    logger.info("[推送占位符] Telegram: %s", content_data.get("title", content_data.get("text", ""))[:50])
    return True


def push_wechat_corporate(corp_id: str, corp_secret: str, agent_id: int, to_user: str, content_data: dict) -> bool:
    """微信企业号推送（保持原有代码）"""
    # 获取 token
    token_url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
    token_params = {"corpid": corp_id, "corpsecret": corp_secret}
    token_resp = requests.get(token_url, params=token_params, timeout=15)
    token_resp.raise_for_status()
    access_token = token_resp.json().get("access_token")
    if not access_token:
        logger.error("微信企业号 token 失败: %s", token_resp.text)
        return False

    news_data = {
        "touser": to_user,
        "msgtype": "news",
        "agentid": agent_id,
        "news": {
            "articles": [
                {
                    "title": content_data.get("title", content_data.get("text", ""))[:64],
                    "description": content_data.get("summary", content_data.get("text", ""))[:200],
                    "url": content_data.get("url", ""),
                    "picurl": content_data.get("image_urls", [""])[0] if content_data.get("image_urls") else ""
                }
            ]
        }
    }

    send_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"
    resp = requests.post(send_url, json=news_data, timeout=15)
    logger.debug("微信企业号推送回应: %s", resp.text)
    return resp.ok and resp.json().get("errcode") == 0


def push_content(content_data: dict, channels: list) -> bool:
    """
    统一推送接口

    content_data: {
        "type": "video" | "dynamic",
        "title": "标题（视频）或动态文本",
        "summary": "摘要（仅视频有）",
        "key_points": [...],
        "tags": [...],
        "images": ["path1", "path2"],  # 本地图片路径
        "image_urls": ["url1", "url2"],  # 图片URLs
        "url": "B站链接",
        "timestamp": "发布时间戳（视频）",
        "pub_time": "发布时间字符串（动态）"
    }

    channels: ["feishu", "telegram", "wechat"]
    """
    content_type = content_data.get("type", "unknown")

    if "feishu" in channels:
        try:
            if content_type == "video":
                push_feishu_video(content_data)
            elif content_type == "dynamic":
                push_feishu_dynamic_card(content_data)
        except Exception as e:
            logger.error("飞书推送异常: %s", e)

    if "telegram" in channels and Config.TELEGRAM_TOKEN and Config.TELEGRAM_CHAT_ID:
        try:
            push_telegram_dynamic(Config.TELEGRAM_TOKEN, Config.TELEGRAM_CHAT_ID, content_data)
        except Exception as e:
            logger.error("Telegram 推送异常: %s", e)

    if "wechat" in channels and Config.WECHAT_CORP_ID and Config.WECHAT_CORP_SECRET and Config.WECHAT_AGENT_ID:
        try:
            push_wechat_corporate(
                Config.WECHAT_CORP_ID,
                Config.WECHAT_CORP_SECRET,
                int(Config.WECHAT_AGENT_ID),
                Config.WECHAT_TO_USER,
                content_data
            )
        except Exception as e:
            logger.error("微信企业号推送异常: %s", e)

    # 记录日志
    if content_type == "video":
        logger.info("[推送] 视频: %s | 标题: %s | 标签: %s",
                    content_data.get("url", ""),
                    content_data.get("title", "")[:50],
                    content_data.get("tags", []))
    elif content_type == "dynamic":
        logger.info("[推送] 动态: %s | 内容: %s | 图片: %d张",
                    content_data.get("url", ""),
                    content_data.get("text", "")[:50],
                    len(content_data.get("images", [])))

    return True
