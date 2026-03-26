#!/usr/bin/env python3
"""
重置数据库中视频的状态为 pending，并清空 summary_json
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.database import get_db, Video
from app.utils.logger import get_logger

logger = get_logger("reset_videos")


def reset_videos():
    """重置所有视频状态"""
    db = get_db()

    # 获取所有视频
    videos = db.query(Video).all()
    logger.info("找到 %d 个视频", len(videos))

    count = 0
    for video in videos:
        old_status = video.status
        old_summary = video.summary_json is not None

        video.status = "pending"
        video.summary_json = None
        video.last_error = None
        video.attempt_count = 0

        count += 1
        logger.info("重置视频: %s | %s | status: %s→pending, summary: %s→NULL",
                    video.bvid, video.title[:30], old_status, old_summary)

    db.commit()
    logger.info("完成！共重置 %d 个视频", count)


if __name__ == "__main__":
    print("正在重置视频状态...")
    reset_videos()
    print("完成！")
