import pytest
import sys
sys.path.insert(0, '.')
from app.modules.dynamic import DynamicFetcher

def test_parse_av_dynamic_extracts_bvid():
    """MAJOR_TYPE_ARCHIVE 动态应提取 bvid"""
    fetcher = DynamicFetcher()
    item = {
        "id_str": "1234567890",
        "type": "DYNAMIC_TYPE_AV",
        "modules": {
            "module_author": {"pub_ts": "1713000000", "pub_time": "2024-04-13"},
            "module_dynamic": {
                "major": {
                    "type": "MAJOR_TYPE_ARCHIVE",
                    "archive": {
                        "bvid": "BV1TEST12345",
                        "title": "测试视频",
                        "desc": "测试描述"
                    }
                }
            }
        }
    }
    result = fetcher._parse_dynamic(item)
    assert result is not None
    assert result.get("bvid") == "BV1TEST12345"
    assert result.get("title") == "测试视频"

def test_parse_non_video_dynamic_no_bvid():
    """非视频动态不应有 bvid"""
    fetcher = DynamicFetcher()
    item = {
        "id_str": "2234567890",
        "type": "DYNAMIC_TYPE_DRAW",
        "modules": {
            "module_author": {"pub_ts": "1713000000", "pub_time": "2024-04-13"},
            "module_dynamic": {
                "major": {
                    "type": "MAJOR_TYPE_COMMON",
                    "common": {"desc": "普通文字"}
                }
            }
        }
    }
    result = fetcher._parse_dynamic(item)
    assert result is not None
    assert "bvid" not in result