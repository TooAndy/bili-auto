#!/usr/bin/env python3
"""
重置数据库中 processing 状态的视频为 pending
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.models.database import get_db, Video, Dynamic
from app.utils.logger import get_logger

logger = get_logger("reset_processing")


def main():
    db = get_db()
    try:
        print("=" * 60)
        print("重置 processing 状态的任务")
        print("=" * 60)
        print()

        # 查找 processing 状态的视频
        processing_videos = db.query(Video).filter_by(status="processing").all()
        print(f"找到 {len(processing_videos)} 个 processing 状态的视频")

        for video in processing_videos:
            print(f"  - {video.bvid}: {video.title}")
            video.status = "pending"
            video.last_error = "手动重置，从 processing 恢复为 pending"

        db.commit()
        print()

        # 查找 processing 状态的动态
        processing_dynamics = db.query(Dynamic).filter_by(status="processing").all()
        print(f"找到 {len(processing_dynamics)} 个 processing 状态的动态")

        for dynamic in processing_dynamics:
            print(f"  - {dynamic.dynamic_id}")
            dynamic.status = "pending"
            dynamic.last_error = "手动重置，从 processing 恢复为 pending"

        db.commit()
        print()

        if processing_videos or processing_dynamics:
            print(f"✓ 已重置 {len(processing_videos)} 个视频, {len(processing_dynamics)} 个动态")
        else:
            print("没有需要重置的任务")

    except Exception as e:
        logger.error("重置失败: %s", e, exc_info=True)
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
