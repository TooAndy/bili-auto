import json
import requests
from datetime import datetime
from app.utils.logger import get_logger
from config import Config

logger = get_logger("push")


def push_content(content_data: dict, channels: list) -> bool:
    """
    统一推送接口
    用户说先不做消息推送，所以仅记录日志
    
    content_data: {
        "type": "video" | "dynamic",
        "title": "标题（视频）或动态文本",
        "summary": "摘要（仅视频有）",
        "key_points": [...],
        "tags": [...],
        "images": ["path1", "path2"],  # 本地图片路径
        "image_urls": ["url1", "url2"],  # 图片URLs
        "url": "B站链接",
        "timestamp": "发布时间"
    }
    
    channels: ["feishu", "telegram", "wechat"] (目前仅记录，不推送)
    """
    content_type = content_data.get("type", "unknown")
    
    if content_type == "video":
        logger.info("[推送占位符] 视频: %s | 标题: %s | 标签: %s",
                    content_data.get("url", ""),
                    content_data.get("title", "")[:50],
                    content_data.get("tags", []))
    elif content_type == "dynamic":
        logger.info("[推送占位符] 动态: %s | 内容: %s | 图片: %d张",
                    content_data.get("url", ""),
                    content_data.get("text", "")[:50],
                    len(content_data.get("images", [])))
    
    logger.debug("推送渠道配置: %s", channels)
    return True


def push_feishu_text(webhook_url: str, content: str) -> bool:
    payload = {
        "msg_type": "text",
        "content": {"text": content}
    }
    resp = requests.post(webhook_url, json=payload, timeout=15)
    if resp.status_code == 200 and resp.json().get("StatusCode") in (0, 200):
        return True
    logger.error("飞书推送失败: %s", resp.text)
    return False


def push_feishu_dynamic_simple(webhook_url: str, dynamic_data: dict) -> bool:
    text = dynamic_data.get("text", "")
    images_text = ""
    for i, url in enumerate(dynamic_data.get("image_urls", [])[:3]):
        images_text += f"\n![图{i+1}]({url})"

    msg = f"📝 动态更新\n\n{text}\n{images_text}\n\n⏰ {dynamic_data.get('pub_time')}\n{dynamic_data.get('url', '')}"
    return push_feishu_text(webhook_url, msg)


def push_telegram_dynamic(bot_token: str, chat_id: str, dynamic_data: dict) -> bool:
    """占位符实现（用户说先不做推送）"""
    logger.info("[推送占位符] Telegram动态: %s", dynamic_data.get("text", "")[:50])
    return True

    bot.send_message(chat_id=chat_id, text=text, parse_mode='HTML')
    return True


def push_wechat_corporate(corp_id: str, corp_secret: str, agent_id: int, to_user, dynamic_data: dict) -> bool:
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
                    "title": dynamic_data.get("text", "")[:64],
                    "description": dynamic_data.get("text", "")[:200],
                    "url": dynamic_data.get("url", ""),
                    "picurl": dynamic_data.get("image_urls", [""])[0] if dynamic_data.get("image_urls") else ""
                }
            ]
        }
    }

    send_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"
    resp = requests.post(send_url, json=news_data, timeout=15)
    logger.debug("微信企业号推送回应: %s", resp.text)
    return resp.ok and resp.json().get("errcode") == 0


def push_content(content_data: dict, channels: list):
    if "feishu" in channels and Config.FEISHU_WEBHOOK:
        try:
            if content_data.get("type") == "dynamic":
                push_feishu_dynamic_simple(Config.FEISHU_WEBHOOK, content_data)
            else:
                push_feishu_text(Config.FEISHU_WEBHOOK, content_data.get("summary", ""))
        except Exception as e:
            logger.error("飞书推送异常: %s", e)

    if "telegram" in channels and Config.TELEGRAM_TOKEN and Config.TELEGRAM_CHAT_ID:
        try:
            if content_data.get("type") == "dynamic":
                push_telegram_dynamic(Config.TELEGRAM_TOKEN, Config.TELEGRAM_CHAT_ID, content_data)
            else:
                from telegram import Bot
                bot = Bot(token=Config.TELEGRAM_TOKEN)
                bot.send_message(chat_id=Config.TELEGRAM_CHAT_ID, text=content_data.get("summary", ""), parse_mode='HTML')
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

    return True
