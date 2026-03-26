"""
测试 bilibili.py - B站 API 模块
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules import bilibili


def test_fetch_channel_videos_success():
    """测试：成功获取 UP 主视频列表"""
    mid = "123456"

    mock_response = {
        "code": 0,
        "data": {
            "list": {
                "vlist": [
                    {
                        "bvid": "BV111",
                        "title": "测试视频1",
                        "created": 1234567890,
                        "length": "10:00",
                        "pic": "https://example.com/1.jpg"
                    },
                    {
                        "bvid": "BV222",
                        "title": "测试视频2",
                        "created": 1234567891,
                        "length": "20:00",
                        "pic": "https://example.com/2.jpg"
                    }
                ]
            }
        }
    }

    with patch('requests.get') as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = mock_response
        mock_get.return_value = mock_resp

        result = bilibili.fetch_channel_videos(mid, limit=5)

    # 验证请求
    mock_get.assert_called_once()
    args, kwargs = mock_get.call_args
    assert kwargs['params']['mid'] == mid
    assert kwargs['params']['ps'] == 5

    # 验证结果
    assert len(result) == 2
    assert result[0]['bvid'] == 'BV111'
    assert result[0]['title'] == '测试视频1'
    assert result[1]['bvid'] == 'BV222'


def test_fetch_channel_videos_code_not_zero():
    """测试：API 返回 code != 0 时返回空列表"""
    mid = "123456"

    mock_response = {
        "code": -1,
        "message": "API error"
    }

    with patch('requests.get') as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = mock_response
        mock_get.return_value = mock_resp

        result = bilibili.fetch_channel_videos(mid)

    assert result == []


def test_fetch_channel_videos_missing_vlist():
    """测试：缺少 vlist 时返回空列表"""
    mid = "123456"

    mock_response = {
        "code": 0,
        "data": {
            "list": {}  # 没有 vlist
        }
    }

    with patch('requests.get') as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = mock_response
        mock_get.return_value = mock_resp

        result = bilibili.fetch_channel_videos(mid)

    assert result == []


def test_fetch_channel_videos_request_exception():
    """测试：网络请求异常时不抛错（需要看实际代码）"""
    mid = "123456"

    with patch('requests.get', side_effect=Exception("Network error")):
        # 实际代码中这里会抛出异常，让调用方处理
        with pytest.raises(Exception):
            bilibili.fetch_channel_videos(mid)


def test_fetch_channel_videos_with_cookie():
    """测试：使用 BILIBILI_COOKIE"""
    mid = "123456"

    mock_response = {"code": 0, "data": {"list": {"vlist": []}}}

    # 直接 patch Config 在 bilibili 模块中的引用
    with patch('app.modules.bilibili.Config') as mock_config:
        mock_config.BILIBILI_COOKIE = "test_cookie_value"

        with patch('requests.get') as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = mock_response
            mock_get.return_value = mock_resp

            bilibili.fetch_channel_videos(mid)

        # 验证 cookie 被加入请求头
        args, kwargs = mock_get.call_args
        assert 'Cookie' in kwargs['headers']
        assert kwargs['headers']['Cookie'] == "test_cookie_value"


def test_get_subtitle_info():
    """测试：获取字幕信息"""
    bvid = "BV1234567890"

    mock_response = {
        "code": 0,
        "data": {
            "subtitle": {
                "list": []
            }
        }
    }

    with patch('requests.get') as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = mock_response
        mock_get.return_value = mock_resp

        result = bilibili.get_subtitle_info(bvid)

    # 验证请求
    mock_get.assert_called_once()
    args, kwargs = mock_get.call_args
    assert kwargs['params']['bvid'] == bvid

    # 验证结果
    assert result == mock_response


def test_get_subtitle_info_with_cid():
    """测试：带 cid 参数获取字幕信息"""
    bvid = "BV1234567890"
    cid = "123456"

    mock_response = {"code": 0, "data": {}}

    with patch('requests.get') as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = mock_response
        mock_get.return_value = mock_resp

        bilibili.get_subtitle_info(bvid, cid=cid)

    # 验证 cid 在参数中
    args, kwargs = mock_get.call_args
    assert kwargs['params']['cid'] == cid
