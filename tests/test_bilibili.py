"""
测试 bilibili.py - B站 API 模块
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules import bilibili


class TestFetchChannelVideos:
    """测试 fetch_channel_videos"""

    def test_fetch_channel_videos_success(self):
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

        mock_session = MagicMock()
        mock_session.get.return_value.json.return_value = mock_response

        with patch('app.modules.bilibili._get_session', return_value=mock_session):
            with patch('app.modules.wbi.sign_params', side_effect=lambda x: x):
                result = bilibili.fetch_channel_videos(mid, limit=5)

        # 验证结果
        assert len(result) == 2
        assert result[0]['bvid'] == 'BV111'
        assert result[0]['title'] == '测试视频1'
        assert result[1]['bvid'] == 'BV222'

    def test_fetch_channel_videos_code_not_zero(self):
        """测试：API 返回 code != 0 时返回空列表"""
        mid = "123456"

        mock_response = {
            "code": -1,
            "message": "API error"
        }

        mock_session = MagicMock()
        mock_session.get.return_value.json.return_value = mock_response

        with patch('app.modules.bilibili._get_session', return_value=mock_session):
            with patch('app.modules.wbi.sign_params', side_effect=lambda x: x):
                result = bilibili.fetch_channel_videos(mid)

        assert result == []

    def test_fetch_channel_videos_missing_vlist(self):
        """测试：缺少 vlist 时返回空列表"""
        mid = "123456"

        mock_response = {
            "code": 0,
            "data": {
                "list": {}  # 没有 vlist
            }
        }

        mock_session = MagicMock()
        mock_session.get.return_value.json.return_value = mock_response

        with patch('app.modules.bilibili._get_session', return_value=mock_session):
            with patch('app.modules.wbi.sign_params', side_effect=lambda x: x):
                result = bilibili.fetch_channel_videos(mid)

        assert result == []


class TestGetSubtitleInfo:
    """测试 get_subtitle_info"""

    def test_get_subtitle_info(self):
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

        mock_session = MagicMock()
        mock_session.get.return_value.json.return_value = mock_response

        with patch('app.modules.bilibili._get_session', return_value=mock_session):
            result = bilibili.get_subtitle_info(bvid)

        # 验证结果
        assert result == mock_response

    def test_get_subtitle_info_with_cid(self):
        """测试：带 cid 参数获取字幕信息"""
        bvid = "BV1234567890"
        cid = "123456"

        mock_response = {"code": 0, "data": {}}

        mock_session = MagicMock()
        mock_session.get.return_value.json.return_value = mock_response

        with patch('app.modules.bilibili._get_session', return_value=mock_session):
            bilibili.get_subtitle_info(bvid, cid=cid)

        # 验证 get 被调用
        mock_session.get.assert_called()


class TestCheckCookie:
    """测试 _check_cookie"""

    def test_check_cookie_raises_when_no_cookie(self):
        """测试：没有配置 cookie 时抛出异常"""
        with patch('config.Config') as mock_cfg:
            mock_cfg.BILIBILI_COOKIE = ""

            with patch('app.modules.bilibili.Config', mock_cfg):
                with pytest.raises(RuntimeError) as exc_info:
                    bilibili._check_cookie()

                assert "BILIBILI_COOKIE" in str(exc_info.value)

    def test_check_cookie_passes_when_cookie_set(self):
        """测试：配置了 cookie 时不抛异常"""
        with patch('config.Config') as mock_cfg:
            mock_cfg.BILIBILI_COOKIE = "test_cookie"

            with patch('app.modules.bilibili.Config', mock_cfg):
                # 不应该抛出异常
                bilibili._check_cookie()
