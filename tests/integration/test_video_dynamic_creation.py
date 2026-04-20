import sys
sys.path.insert(0, '.')
from unittest.mock import patch
from app.modules.dynamic import DynamicFetcher
from app.models.database import get_db, Video, Dynamic
from app.scheduler import check_new_dynamics

def test_video_dynamic_creates_both_records():
    """视频动态应同时创建 Dynamic 和 Video 记录"""
    with patch.object(DynamicFetcher, 'fetch_dynamic') as mock_fetch:
        mock_fetch.return_value = [{
            "dynamic_id": "TEST123",
            "type": "DYNAMIC_TYPE_AV",
            "bvid": "BV1TEST12345",
            "title": "测试视频",
            "text": "",
            "image_urls": [],
            "images": [],
            "pub_ts": 1713000000,
            "mid": "322005137",
            "sub_name": "呆咪"
        }]

        db = get_db()
        db.query(Video).filter_by(bvid="BV1TEST12345").delete()
        db.query(Dynamic).filter_by(dynamic_id="TEST123").delete()
        db.commit()

        check_new_dynamics()

        video = db.query(Video).filter_by(bvid="BV1TEST12345").first()
        assert video is not None, "Video 记录未创建"
        assert video.title == "测试视频"

        dynamic = db.query(Dynamic).filter_by(dynamic_id="TEST123").first()
        assert dynamic is not None, "Dynamic 记录未创建"
        assert dynamic.video_bvid == "BV1TEST12345"

        db.close()