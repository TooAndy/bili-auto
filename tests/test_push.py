"""
测试 push.py - 飞书推送模块
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from app.modules import push
from config import Config


def test_get_feishu_tenant_access_token_success():
    """测试：成功获取 tenant_access_token"""
    with patch('requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 0,
            "tenant_access_token": "test_token_123",
            "expire": 7200
        }
        mock_post.return_value = mock_response

        # 清空缓存
        push._feishu_token_cache = None
        push._feishu_token_expire_at = 0

        token = push.get_feishu_tenant_access_token()

        assert token == "test_token_123"
        assert push._feishu_token_cache == "test_token_123"


def test_get_feishu_tenant_access_token_failure():
    """测试：获取 tenant_access_token 失败"""
    with patch('requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 10013,
            "msg": "invalid app_id"
        }
        mock_post.return_value = mock_response

        push._feishu_token_cache = None
        token = push.get_feishu_tenant_access_token()

        assert token is None


def test_get_feishu_tenant_access_token_no_config():
    """测试：未配置 APP_ID/APP_SECRET 时返回 None"""
    with patch('config.Config') as mock_cfg:
        mock_cfg.FEISHU_APP_ID = ""
        mock_cfg.FEISHU_APP_SECRET = ""

        # 临时替换 Config
        original_config = push.Config
        push.Config = mock_cfg
        try:
            token = push.get_feishu_tenant_access_token()
            assert token is None
        finally:
            push.Config = original_config


def test_get_feishu_tenant_access_token_uses_cache():
    """测试：使用缓存的 token"""
    push._feishu_token_cache = "cached_token"
    push._feishu_token_expire_at = 9999999999  # 未来时间

    with patch('requests.post') as mock_post:
        token = push.get_feishu_tenant_access_token()

        assert token == "cached_token"
        mock_post.assert_not_called()


def test_push_feishu_text_by_webhook_success():
    """测试：webhook 推送成功"""
    with patch('requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"StatusCode": 0}
        mock_post.return_value = mock_response

        result = push.push_feishu_text_by_webhook("https://webhook.url", "测试消息")

        assert result is True


def test_push_feishu_text_by_webhook_failure():
    """测试：webhook 推送失败"""
    with patch('requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_post.return_value = mock_response

        result = push.push_feishu_text_by_webhook("https://webhook.url", "测试消息")

        assert result is False


def test_push_feishu_text_by_app_success():
    """测试：应用模式推送成功"""
    with patch('app.modules.push.get_feishu_tenant_access_token', return_value="test_token"):
        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"code": 0}
            mock_post.return_value = mock_response

            with patch('config.Config') as mock_cfg:
                mock_cfg.FEISHU_RECEIVE_ID_TYPE = "open_id"
                mock_cfg.FEISHU_RECEIVE_ID = "ou_123"
                original_config = push.Config
                push.Config = mock_cfg
                try:
                    result = push.push_feishu_text_by_app("测试消息")
                    assert result is True
                finally:
                    push.Config = original_config


def test_push_feishu_text_by_app_no_token():
    """测试：没有 token 时推送失败"""
    with patch('app.modules.push.get_feishu_tenant_access_token', return_value=None):
        result = push.push_feishu_text_by_app("测试消息")
        assert result is False


def test_push_feishu_video():
    """测试：视频消息推送"""
    video_data = {
        "title": "测试视频",
        "summary": "这是摘要",
        "tags": ["科技", "测试"],
        "url": "https://www.bilibili.com/video/BV123"
    }

    with patch('app.modules.push.push_feishu_text', return_value=True) as mock_push:
        result = push.push_feishu_video(video_data)

        assert result is True
        mock_push.assert_called_once()
        # 验证调用参数包含视频信息
        call_args = mock_push.call_args[0][0]
        assert "测试视频" in call_args
        assert "这是摘要" in call_args
        assert "#科技" in call_args


def test_push_feishu_dynamic():
    """测试：动态消息推送"""
    dynamic_data = {
        "text": "这是一条动态",
        "pub_time": "2024-03-31 18:00",
        "url": "https://www.bilibili.com/opus/123"
    }

    with patch('app.modules.push.push_feishu_text', return_value=True) as mock_push:
        result = push.push_feishu_dynamic(dynamic_data)

        assert result is True
        mock_push.assert_called_once()
        call_args = mock_push.call_args[0][0]
        assert "这是一条动态" in call_args
        assert "2024-03-31" in call_args


def test_push_content_feishu_channel():
    """测试：统一推送接口 - 飞书渠道"""
    content_data = {
        "type": "video",
        "title": "测试视频",
        "url": "https://www.bilibili.com/video/BV123"
    }

    with patch('app.modules.push.push_feishu_video') as mock_video:
        result = push.push_content(content_data, ["feishu"])

        assert result is True
        mock_video.assert_called_once_with(content_data)


def test_push_content_dynamic_type():
    """测试：统一推送接口 - 动态类型"""
    content_data = {
        "type": "dynamic",
        "text": "测试动态",
        "url": "https://www.bilibili.com/opus/123"
    }

    with patch('app.modules.push.push_feishu_dynamic') as mock_dynamic:
        push.push_content(content_data, ["feishu"])

        mock_dynamic.assert_called_once_with(content_data)


def test_push_content_handles_exception():
    """测试：推送异常时不崩溃"""
    content_data = {
        "type": "video",
        "title": "测试视频"
    }

    with patch('app.modules.push.push_feishu_video', side_effect=Exception("推送失败")):
        # 异常应该被捕获，不会抛出
        result = push.push_content(content_data, ["feishu"])
        assert result is True
