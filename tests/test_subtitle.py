"""
测试 subtitle.py - 字幕获取模块
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules import subtitle


def test_get_subtitles_success():
    """测试：成功获取字幕"""
    bvid = "BV1234567890"

    # Mock get_subtitle_info
    mock_subtitle_info = {
        "data": {
            "subtitle": {
                "list": [
                    {
                        "subtitle_url": "https://example.com/subtitle.json",
                        "lan_url": "https://example.com/subtitle.json"
                    }
                ]
            }
        }
    }

    # Mock requests.get
    mock_subtitle_json = {
        "body": [
            {"content": "第一句话"},
            {"content": "第二句话"},
            {"content": "第三句话"}
        ]
    }

    with patch('app.modules.subtitle.get_subtitle_info', return_value=mock_subtitle_info):
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = mock_subtitle_json
            mock_get.return_value = mock_response

            result = subtitle.get_subtitles(bvid)

    # 验证结果
    assert "第一句话" in result
    assert "第二句话" in result
    assert "第三句话" in result
    assert len(result.splitlines()) == 3


def test_get_subtitles_no_subtitle_list():
    """测试：没有字幕列表时返回空字符串"""
    bvid = "BV1234567890"

    mock_subtitle_info = {
        "data": {
            "subtitle": {
                "list": []  # 空列表
            }
        }
    }

    with patch('app.modules.subtitle.get_subtitle_info', return_value=mock_subtitle_info):
        result = subtitle.get_subtitles(bvid)

    assert result == ""


def test_get_subtitles_missing_subtitle_key():
    """测试：缺少字幕键时返回空字符串"""
    bvid = "BV1234567890"

    mock_subtitle_info = {
        "data": {}  # 没有 subtitle 键
    }

    with patch('app.modules.subtitle.get_subtitle_info', return_value=mock_subtitle_info):
        result = subtitle.get_subtitles(bvid)

    assert result == ""


def test_get_subtitles_request_fails():
    """测试：字幕请求失败时返回空字符串"""
    bvid = "BV1234567890"

    mock_subtitle_info = {
        "data": {
            "subtitle": {
                "list": [
                    {"subtitle_url": "https://example.com/subtitle.json"}
                ]
            }
        }
    }

    with patch('app.modules.subtitle.get_subtitle_info', return_value=mock_subtitle_info):
        with patch('requests.get', side_effect=Exception("Network error")):
            result = subtitle.get_subtitles(bvid)

    # 即使请求失败也应该返回空字符串，不抛出异常
    assert result == ""


def test_get_subtitles_no_url_in_subtitle_item():
    """测试：字幕项中没有 URL 时跳过"""
    bvid = "BV1234567890"

    mock_subtitle_info = {
        "data": {
            "subtitle": {
                "list": [
                    {},  # 没有 subtitle_url 或 lan_url
                    {"subtitle_url": "https://example.com/sub.json"}
                ]
            }
        }
    }

    mock_subtitle_json = {
        "body": [{"content": "有效内容"}]
    }

    with patch('app.modules.subtitle.get_subtitle_info', return_value=mock_subtitle_info):
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = mock_subtitle_json
            mock_get.return_value = mock_response

            result = subtitle.get_subtitles(bvid)

    # 应该只获取第二个字幕项的内容
    assert "有效内容" in result


def test_get_subtitles_exception_returns_empty():
    """测试：任何异常都返回空字符串"""
    bvid = "BV1234567890"

    # Mock get_subtitle_info 抛出异常
    with patch('app.modules.subtitle.get_subtitle_info', side_effect=Exception("API error")):
        result = subtitle.get_subtitles(bvid)

    assert result == ""


def test_get_subtitles_body_not_list():
    """测试：body 不是列表时的处理"""
    bvid = "BV1234567890"

    mock_subtitle_info = {
        "data": {
            "subtitle": {
                "list": [{"subtitle_url": "https://example.com/sub.json"}]
            }
        }
    }

    # body 是字符串而不是列表
    mock_subtitle_json = {
        "body": "not a list"
    }

    with patch('app.modules.subtitle.get_subtitle_info', return_value=mock_subtitle_info):
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = mock_subtitle_json
            mock_get.return_value = mock_response

            result = subtitle.get_subtitles(bvid)

    # 应该优雅处理，返回空字符串
    assert result == ""
