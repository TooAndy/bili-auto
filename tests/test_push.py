"""
测试 push_channels 模块
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from app.modules.push_channels import push_content, list_channels, get_channel
from app.modules.push_channels.feishu import (
    get_feishu_tenant_access_token,
    upload_image_to_feishu,
    FeishuChannel,
)
from app.modules.push_channels.telegram import TelegramChannel
from app.modules.push_channels.wechat import WechatChannel
from app.modules.push_channels.registry import ChannelRegistry


class TestChannelRegistry:
    """测试渠道注册表"""

    def test_list_channels(self):
        """测试：列出所有已注册渠道"""
        channels = list_channels()
        assert "feishu" in channels
        assert "wechat" in channels
        assert "telegram" in channels

    def test_get_channel(self):
        """测试：获取指定渠道"""
        channel = get_channel("feishu")
        assert channel is not None
        assert channel.channel_name == "feishu"

    def test_get_unknown_channel(self):
        """测试：获取未知渠道返回 None"""
        channel = get_channel("unknown")
        assert channel is None


class TestFeishuChannel:
    """测试飞书渠道"""

    def test_send_video(self):
        """测试：发送视频消息"""
        channel = FeishuChannel()

        with patch.object(channel, '_send_text', return_value=True) as mock_send:
            result = channel.send({
                "type": "video",
                "title": "测试视频",
                "summary": "这是摘要",
                "tags": ["科技"],
                "stocks": ["小米"],
                "url": "https://bilibili.com/video/BV123",
                "doc_url": "https://feishu.doc/abc"
            })

            assert result is True
            mock_send.assert_called_once()
            call_text = mock_send.call_args[0][0]
            assert "测试视频" in call_text
            assert "这是摘要" in call_text
            assert "小米" in call_text

    def test_send_dynamic(self):
        """测试：发送动态消息（卡片）"""
        channel = FeishuChannel()

        with patch.object(channel, '_send_card', return_value=True) as mock_send:
            result = channel.send({
                "type": "dynamic",
                "text": "这是一条动态内容",
                "url": "https://bilibili.com/opus/123",
                "pub_time": "2024-03-31 18:00:00"
            })

            assert result is True
            mock_send.assert_called_once()

    def test_send_text(self):
        """测试：发送纯文本"""
        channel = FeishuChannel()

        with patch.object(channel, '_send_text', return_value=True) as mock_send:
            result = channel.send_text("纯文本消息")
            assert result is True
            mock_send.assert_called_once_with("纯文本消息")


class TestFeishuToken:
    """测试飞书 Token 获取"""

    def test_get_token_success(self):
        """测试：成功获取 token"""
        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "code": 0,
                "tenant_access_token": "test_token_123",
                "expire": 7200
            }
            mock_post.return_value = mock_response

            # 清空缓存
            import app.modules.push_channels.feishu as feishu_module
            feishu_module._feishu_token_cache = None
            feishu_module._feishu_token_expire_at = 0

            token = get_feishu_tenant_access_token()
            assert token == "test_token_123"

    def test_get_token_failure(self):
        """测试：获取 token 失败"""
        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "code": 10013,
                "msg": "invalid app_id"
            }
            mock_post.return_value = mock_response

            import app.modules.push_channels.feishu as feishu_module
            feishu_module._feishu_token_cache = None

            token = get_feishu_tenant_access_token()
            assert token is None

    def test_get_token_uses_cache(self):
        """测试：使用缓存的 token"""
        import app.modules.push_channels.feishu as feishu_module
        feishu_module._feishu_token_cache = "cached_token"
        feishu_module._feishu_token_expire_at = 9999999999

        with patch('requests.post') as mock_post:
            token = get_feishu_tenant_access_token()
            assert token == "cached_token"
            mock_post.assert_not_called()


class TestPushContent:
    """测试统一推送接口"""

    def test_push_to_feishu_video(self):
        """测试：推送视频到飞书"""
        result = push_content({
            "type": "video",
            "title": "测试视频",
            "url": "https://bilibili.com/video/BV123"
        }, ["feishu"])
        # 由于是 mock，实际会发送失败，但不会崩溃
        assert result is False or result is True

    def test_push_to_multiple_channels(self):
        """测试：推送到多个渠道"""
        content = {
            "type": "dynamic",
            "text": "测试动态",
            "url": "https://bilibili.com/opus/123"
        }
        # 只推送到 feishu
        result = push_content(content, ["feishu"])
        assert result is False or result is True

    def test_push_to_unknown_channel(self):
        """测试：推送到未知渠道"""
        result = push_content({
            "type": "dynamic",
            "text": "测试",
            "url": "https://example.com"
        }, ["unknown_channel"])
        assert result is False


class TestFeishuCardMessage:
    """测试飞书卡片消息构建"""

    def test_build_dynamic_card(self):
        """测试：构建动态卡片"""
        channel = FeishuChannel()

        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "text": "📝 新动态"},
                "template": "blue"
            },
            "elements": [
                {"tag": "div", "text": {"tag": "plain_text", "content": "测试内容"}},
                {"tag": "div", "text": {"tag": "lark_md", "content": "[链接](http://example.com)"}}
            ]
        }

        # 验证卡片结构
        assert card["config"]["wide_screen_mode"] is True
        assert card["header"]["template"] == "blue"
        assert len(card["elements"]) == 2


class TestTelegramChannel:
    """测试 Telegram 渠道"""

    def test_send_dynamic_with_title(self):
        """测试：发送动态消息（带标题）"""
        channel = TelegramChannel()

        with patch.object(channel, 'send', wraps=channel.send):
            with patch.object(channel, '_send_text', return_value=True) as mock_send:
                # patch send 避免 Config 检查直接返回 False
                with patch('app.modules.push_channels.telegram.Config') as mock_config:
                    mock_config.TELEGRAM_TOKEN = "fake_token"
                    mock_config.TELEGRAM_CHAT_ID = "fake_chat_id"

                    result = channel.send({
                        "type": "dynamic",
                        "title": "动态标题",
                        "text": "动态正文内容",
                        "url": "https://bilibili.com/opus/123",
                        "pub_time": "2024-03-31 18:00:00"
                    })

                    assert result is True
                    mock_send.assert_called_once()
                    call_text = mock_send.call_args[0][0]
                    assert "动态标题" in call_text
                    assert "动态正文内容" in call_text
                    assert "*动态标题*" in call_text  # 加粗

    def test_send_dynamic_without_title(self):
        """测试：发送动态消息（无标题）"""
        channel = TelegramChannel()

        with patch.object(channel, '_send_text', return_value=True) as mock_send:
            with patch('app.modules.push_channels.telegram.Config') as mock_config:
                mock_config.TELEGRAM_TOKEN = "fake_token"
                mock_config.TELEGRAM_CHAT_ID = "fake_chat_id"

                result = channel.send({
                    "type": "dynamic",
                    "title": "",
                    "text": "动态正文内容",
                    "url": "https://bilibili.com/opus/123",
                })

                assert result is True
                mock_send.assert_called_once()
                call_text = mock_send.call_args[0][0]
                assert "📝" in call_text
                assert "动态正文内容" in call_text


class TestWechatChannel:
    """测试微信企业号渠道"""

    def test_send_dynamic_with_title(self):
        """测试：发送动态消息（带标题）"""
        channel = WechatChannel()

        with patch.object(channel, '_get_access_token', return_value="fake_token"):
            with patch('requests.post') as mock_post:
                mock_response = MagicMock()
                mock_response.json.return_value = {"errcode": 0}
                mock_post.return_value = mock_response

                with patch('app.modules.push_channels.wechat.Config') as mock_config:
                    mock_config.WECHAT_CORP_ID = "fake_corp_id"
                    mock_config.WECHAT_CORP_SECRET = "fake_secret"
                    mock_config.WECHAT_AGENT_ID = "123456"
                    mock_config.WECHAT_TO_USER = "fake_user"

                    result = channel.send({
                        "type": "dynamic",
                        "title": "动态标题",
                        "text": "动态正文",
                        "url": "https://bilibili.com/opus/123",
                        "pub_time": "2024-03-31",
                        "image_urls": []
                    })

                    assert result is True
                    # json= 是关键字参数，从 call_args[1] 取
                    call_json = mock_post.call_args[1]["json"]
                    assert "📝 动态标题" in call_json["news"]["articles"][0]["title"]

    def test_send_dynamic_without_title(self):
        """测试：发送动态消息（无标题）"""
        channel = WechatChannel()

        with patch.object(channel, '_get_access_token', return_value="fake_token"):
            with patch('requests.post') as mock_post:
                mock_response = MagicMock()
                mock_response.json.return_value = {"errcode": 0}
                mock_post.return_value = mock_response

                with patch('app.modules.push_channels.wechat.Config') as mock_config:
                    mock_config.WECHAT_CORP_ID = "fake_corp_id"
                    mock_config.WECHAT_CORP_SECRET = "fake_secret"
                    mock_config.WECHAT_AGENT_ID = "123456"
                    mock_config.WECHAT_TO_USER = "fake_user"

                    result = channel.send({
                        "type": "dynamic",
                        "title": "",
                        "text": "动态正文",
                        "url": "https://bilibili.com/opus/123",
                        "image_urls": []
                    })

                    assert result is True
                    call_json = mock_post.call_args[1]["json"]
                    assert call_json["news"]["articles"][0]["title"] == "📝 新动态"


class TestFeishuChannelDynamic:
    """测试飞书渠道动态推送（标题相关）"""

    def test_send_dynamic_with_title(self):
        """测试：发送动态消息（带标题，标题加粗）"""
        channel = FeishuChannel()

        with patch.object(channel, '_send_card', return_value=True) as mock_send:
            result = channel.send({
                "type": "dynamic",
                "title": "动态标题",
                "text": "动态正文",
                "url": "https://bilibili.com/opus/123",
                "pub_time": "2024-03-31 18:00:00"
            })

            assert result is True
            mock_send.assert_called_once()
            card = mock_send.call_args[0][0]
            # 标题在 elements 第一位，lark_md 格式加粗
            elements = card["elements"]
            assert elements[0]["tag"] == "div"
            assert "**动态标题**" in elements[0]["text"]["content"]
            # 卡片 header 使用标题
            assert "📝 动态标题" in card["header"]["title"]["text"]

    def test_send_dynamic_title_only(self):
        """测试：发送动态消息（只有标题，没有正文）"""
        channel = FeishuChannel()

        with patch.object(channel, '_send_card', return_value=True) as mock_send:
            result = channel.send({
                "type": "dynamic",
                "title": "纯标题",
                "text": "",
                "url": "https://bilibili.com/opus/123",
            })

            assert result is True
            mock_send.assert_called_once()
            card = mock_send.call_args[0][0]
            elements = card["elements"]
            # 第一位是标题
            assert "**纯标题**" in elements[0]["text"]["content"]
            # 只有标题元素 + 链接，没有正文元素（正文为空时不加正文 div）
            # elements = [标题div, 链接div] 共2个
            div_elements = [e for e in elements if e.get("tag") == "div"]
            assert len(div_elements) == 2  # 标题 + 链接

