"""
测试 dynamic 模块
"""
import pytest
from datetime import datetime

from app.modules.dynamic import DynamicFetcher, should_push_dynamic


class TestParseDynamic:
    """测试动态解析"""

    def _make_fetcher(self):
        """创建 fetcher 实例"""
        return DynamicFetcher()

    def _item(self, modules, id_str="123", type_str="DYNAMIC_TYPE_OPUS", orig=None):
        """构造动态数据"""
        return {
            "id_str": id_str,
            "type": type_str,
            "orig": orig,
            "modules": modules,
        }

    def _modules(self, author_ts=1700000000, author_time="2024-01-01 12:00:00", major_type="MAJOR_TYPE_OPUS",
                  major=None, dynamic=None):
        """构造 modules 结构"""
        return {
            "module_author": {
                "pub_ts": str(author_ts),
                "pub_time": author_time,
            },
            "module_dynamic": {
                "major": {"type": major_type, major_type: major} if major else None,
            },
            "module_dynamic": dynamic or {"major": {"type": major_type} if major_type else {}},
        }

    def test_parse_opus_with_title_and_summary(self):
        """测试：OPUS 动态有标题+正文"""
        fetcher = self._make_fetcher()
        item = self._item(
            modules={
                "module_author": {"pub_ts": "1700000000", "pub_time": "2024-01-01 12:00:00"},
                "module_dynamic": {
                    "major": {
                        "type": "MAJOR_TYPE_OPUS",
                        "opus": {
                            "title": "这是动态标题",
                            "summary": {"text": "这是动态正文内容"},
                            "pics": [],
                        }
                    }
                }
            },
            id_str="opus_001",
        )
        result = fetcher._parse_dynamic(item)

        assert result is not None
        assert result["dynamic_id"] == "opus_001"
        assert result["title"] == "这是动态标题"
        assert result["text"] == "这是动态正文内容"

    def test_parse_opus_with_title_only(self):
        """测试：OPUS 动态只有标题，没有正文"""
        fetcher = self._make_fetcher()
        item = self._item(
            modules={
                "module_author": {"pub_ts": "1700000000", "pub_time": "2024-01-01 12:00:00"},
                "module_dynamic": {
                    "major": {
                        "type": "MAJOR_TYPE_OPUS",
                        "opus": {
                            "title": "纯标题动态",
                            "summary": {"text": ""},
                            "pics": [],
                        }
                    }
                }
            },
            id_str="opus_002",
        )
        result = fetcher._parse_dynamic(item)

        assert result is not None
        assert result["title"] == "纯标题动态"
        assert result["text"] == ""

    def test_parse_opus_with_summary_string(self):
        """测试：OPUS 动态 summary 是字符串而非 dict"""
        fetcher = self._make_fetcher()
        item = self._item(
            modules={
                "module_author": {"pub_ts": "1700000000", "pub_time": "2024-01-01 12:00:00"},
                "module_dynamic": {
                    "major": {
                        "type": "MAJOR_TYPE_OPUS",
                        "opus": {
                            "title": "标题",
                            "summary": "字符串类型的正文",
                            "pics": [],
                        }
                    }
                }
            },
            id_str="opus_003",
        )
        result = fetcher._parse_dynamic(item)

        assert result is not None
        assert result["title"] == "标题"
        assert result["text"] == "字符串类型的正文"

    def test_parse_archive_with_title_and_desc(self):
        """测试：视频动态有标题和描述"""
        fetcher = self._make_fetcher()
        item = self._item(
            modules={
                "module_author": {"pub_ts": "1700000000", "pub_time": "2024-01-01 12:00:00"},
                "module_dynamic": {
                    "major": {
                        "type": "MAJOR_TYPE_ARCHIVE",
                        "archive": {
                            "title": "视频标题",
                            "desc": "视频描述内容",
                        }
                    }
                }
            },
            id_str="av_001",
            type_str="DYNAMIC_TYPE_AV",
        )
        result = fetcher._parse_dynamic(item)

        assert result is not None
        assert result["title"] == "视频标题"
        assert result["text"] == "视频描述内容"

    def test_parse_common_with_text_and_images(self):
        """测试：普通动态有文字和图片"""
        fetcher = self._make_fetcher()
        item = self._item(
            modules={
                "module_author": {"pub_ts": "1700000000", "pub_time": "2024-01-01 12:00:00"},
                "module_dynamic": {
                    "major": {
                        "type": "MAJOR_TYPE_COMMON",
                        "common": {
                            "desc": "普通动态文字",
                            "images": [
                                {"src": "https://example.com/img1.jpg"},
                                {"src": "https://example.com/img2.jpg"},
                            ]
                        }
                    }
                }
            },
            id_str="common_001",
            type_str="DYNAMIC_TYPE_DRAW",
        )
        result = fetcher._parse_dynamic(item)

        assert result is not None
        assert result["title"] == ""
        assert result["text"] == "普通动态文字"
        assert result["image_urls"] == ["https://example.com/img1.jpg", "https://example.com/img2.jpg"]

    def test_parse_forward_returns_none(self):
        """测试：转发动态返回 None"""
        fetcher = self._make_fetcher()
        item = {
            "id_str": "forward_001",
            "type": "DYNAMIC_TYPE_FORWARD",
            "orig": {"dynamic_id": "orig_001"},  # 有 orig 说明是转发
            "modules": {
                "module_author": {"pub_ts": "1700000000", "pub_time": "2024-01-01 12:00:00"},
                "module_dynamic": {"major": {}}
            }
        }
        result = fetcher._parse_dynamic(item)

        assert result is None

    def test_parse_empty_returns_none(self):
        """测试：既没有标题也没有正文的动态返回 None"""
        fetcher = self._make_fetcher()
        item = self._item(
            modules={
                "module_author": {"pub_ts": "1700000000", "pub_time": "2024-01-01 12:00:00"},
                "module_dynamic": {
                    "major": {
                        "type": "MAJOR_TYPE_OPUS",
                        "opus": {
                            "title": "",
                            "summary": {"text": ""},
                            "pics": [],
                        }
                    }
                }
            },
            id_str="empty_001",
        )
        result = fetcher._parse_dynamic(item)

        assert result is None

    def test_parse_pub_time_converted_to_datetime(self):
        """测试：发布时间戳被转换为 datetime 对象"""
        fetcher = self._make_fetcher()
        item = self._item(
            modules={
                "module_author": {"pub_ts": "1704067200", "pub_time": "2024-01-01 12:00:00"},
                "module_dynamic": {
                    "major": {
                        "type": "MAJOR_TYPE_OPUS",
                        "opus": {
                            "title": "标题",
                            "summary": {"text": "正文"},
                            "pics": [],
                        }
                    }
                }
            },
            id_str="time_001",
        )
        result = fetcher._parse_dynamic(item)

        assert result is not None
        assert result["pub_time"] is not None
        assert isinstance(result["pub_time"], datetime)


class TestShouldPushDynamic:
    """测试 should_push_dynamic"""

    def test_has_text_passes(self):
        """测试：有正文可以通过过滤"""
        assert should_push_dynamic({"text": "这是一条有内容的动态，不少于10个字"}) is True

    def test_has_title_only_passes(self):
        """测试：只有标题可以通过过滤（新增行为）"""
        assert should_push_dynamic({"title": "纯标题动态", "text": ""}) is True

    def test_empty_returns_false(self):
        """测试：标题和正文都为空返回 False"""
        assert should_push_dynamic({"title": "", "text": ""}) is False
        assert should_push_dynamic({"title": None, "text": None}) is False

    def test_forward_filtered(self):
        """测试：转发内容被过滤"""
        assert should_push_dynamic({"text": "转发 @用户: 原动态内容"}) is False
        assert should_push_dynamic({"text": "//@用户: 原动态"}) is False

    def test_url_only_short_filtered(self):
        """测试：短链接被过滤"""
        assert should_push_dynamic({"text": "https://bilibili.com/abc"}) is False

    def test_url_only_long_passes(self):
        """测试：长文本链接可以通过"""
        assert should_push_dynamic({"text": "这是一段比较长的文本内容，https://bilibili.com/abcdefghijk，不算短链接，可以推送出去，不少于10个字"}) is True

    def test_too_short_filtered(self):
        """测试：太短的正文被过滤"""
        assert should_push_dynamic({"text": "太短"}) is False

    def test_banned_keywords_filtered(self):
        """测试：包含敏感词的被过滤"""
        assert should_push_dynamic({"text": "限时优惠，快来秒杀！"}) is False
        assert should_push_dynamic({"text": "今日折扣商品"}) is False

    def test_title_with_short_text_filtered(self):
        """测试：有标题但正文太短仍被过滤（正文关键字检查）"""
        # 只有标题没有正文可以过，但有正文时需要满足正文条件
        assert should_push_dynamic({"title": "标题", "text": "秒杀"}) is False

    def test_title_no_text_passes(self):
        """测试：有标题但无正文可以通过（主要用例：纯标题 OPUS 动态）"""
        assert should_push_dynamic({"title": "这是一个有意义的标题", "text": ""}) is True
