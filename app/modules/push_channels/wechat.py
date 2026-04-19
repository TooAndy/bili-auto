from typing import Dict, Any

import requests

from app.modules.push_channels.base import BaseChannel
from app.modules.push_channels.registry import ChannelRegistry
from app.utils.logger import get_logger
from config import Config

logger = get_logger("push.wechat")


@ChannelRegistry.register
class WechatChannel(BaseChannel):
    """微信企业号推送渠道"""

    channel_name = "wechat"

    def send(self, content_data: Dict[str, Any]) -> bool:
        """推送消息到微信企业号"""
        if not Config.WECHAT_CORP_ID or not Config.WECHAT_CORP_SECRET or not Config.WECHAT_AGENT_ID:
            logger.debug("微信企业号未配置")
            return False

        content_type = content_data.get("type", "unknown")

        if content_type == "video":
            return self._send_video(content_data)
        elif content_type == "dynamic":
            return self._send_dynamic(content_data)
        else:
            return self._send_video(content_data)

    def _send_video(self, content_data: Dict[str, Any]) -> bool:
        """推送视频消息"""
        title = content_data.get("title", "无标题")
        summary = content_data.get("summary", "")
        url = content_data.get("url", "")

        # 获取 access_token
        token = self._get_access_token()
        if not token:
            return False

        # 构建图文消息
        news_data = {
            "touser": Config.WECHAT_TO_USER,
            "msgtype": "news",
            "agentid": int(Config.WECHAT_AGENT_ID),
            "news": {
                "articles": [
                    {
                        "title": title[:64],
                        "description": (summary or content_data.get("text", ""))[:200],
                        "url": url,
                        "picurl": (content_data.get("image_urls") or [""])[0]
                    }
                ]
            }
        }

        send_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
        try:
            resp = requests.post(send_url, json=news_data, timeout=15)
            result = resp.json()
            return result.get("errcode") == 0
        except Exception as e:
            logger.error("微信推送异常: %s", e)
            return False

    def _send_dynamic(self, content_data: Dict[str, Any]) -> bool:
        """推送动态消息"""
        title = content_data.get("title", "")
        text = content_data.get("text", "")
        url = content_data.get("url", "")
        pub_time = content_data.get("pub_time", "")

        # 截断文本
        display_text = text[:500]
        if len(text) > 500:
            display_text += "..."

        description = display_text
        if pub_time:
            description = f"⏰ {pub_time}\n\n{description}"

        # 获取 access_token
        token = self._get_access_token()
        if not token:
            return False

        # 构建图文消息
        news_data = {
            "touser": Config.WECHAT_TO_USER,
            "msgtype": "news",
            "agentid": int(Config.WECHAT_AGENT_ID),
            "news": {
                "articles": [
                    {
                        "title": f"📝 {title}" if title else "📝 新动态",
                        "description": description[:200],
                        "url": url,
                        "picurl": (content_data.get("image_urls") or [""])[0]
                    }
                ]
            }
        }

        send_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
        try:
            resp = requests.post(send_url, json=news_data, timeout=15)
            result = resp.json()
            return result.get("errcode") == 0
        except Exception as e:
            logger.error("微信推送异常: %s", e)
            return False

    def _get_access_token(self) -> str:
        """获取 access_token"""
        token_url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
        params = {"corpid": Config.WECHAT_CORP_ID, "corpsecret": Config.WECHAT_CORP_SECRET}
        try:
            resp = requests.get(token_url, params=params, timeout=15)
            result = resp.json()
            if result.get("errcode") == 0:
                return result.get("access_token", "")
            else:
                logger.error("微信 token 获取失败: %s", result.get("errmsg"))
                return ""
        except Exception as e:
            logger.error("微信 token 请求异常: %s", e)
            return ""
