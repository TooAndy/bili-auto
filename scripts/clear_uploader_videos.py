#!/usr/bin/env python3
"""
清理指定 UP主的所有视频数据

删除：
- 数据库中的视频记录
- 视频文件
- 音频文件
- 文本文件
- Markdown文件
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.models.database import get_db, Video
from app.utils.logger import get_logger

logger = get_logger("clear_videos")


def clear_uploader_videos(mid: str, confirm: bool = False):
    """
    清理指定 UP主的所有视频数据

    Args:
        mid: UP主 ID
        confirm: 是否确认删除（不确认则只显示预览）
    """
    db = get_db()
    try:
        # 查询该 UP主的所有视频
        videos = db.query(Video).filter_by(mid=mid).all()

        if not videos:
            print(f"未找到 UP主 {mid} 的视频")
            return

        print(f"找到 {len(videos)} 个视频")
        print()

        # 统计文件
        video_files = []
        audio_files = []
        text_files = []
        markdown_files = []

        for video in videos:
            bvid = video.bvid

            # 视频文件
            if video.video_path:
                video_files.append(Path(video.video_path))
            else:
                video_path = Path("data/video") / f"{bvid}.mp4"
                if video_path.exists():
                    video_files.append(video_path)

            # 音频文件
            if video.audio_path:
                audio_files.append(Path(video.audio_path))
            else:
                audio_path = Path("data/audio") / f"{bvid}.m4a"
                if audio_path.exists():
                    audio_files.append(audio_path)

            # 文本文件
            text_path = Path("data/text") / f"{bvid}.txt"
            if text_path.exists():
                text_files.append(text_path)

            # Markdown文件
            md_path = Path("data/markdown") / f"{bvid}.md"
            if md_path.exists():
                markdown_files.append(md_path)

        # 显示预览
        print("=" * 60)
        print("预览：将删除以下内容")
        print("=" * 60)
        print(f"数据库记录: {len(videos)} 条")
        print(f"视频文件: {len(video_files)} 个")
        print(f"音频文件: {len(audio_files)} 个")
        print(f"文本文件: {len(text_files)} 个")
        print(f"Markdown文件: {len(markdown_files)} 个")
        print()

        # 显示前5个视频
        print("视频列表（前5个）:")
        for i, video in enumerate(videos[:5], 1):
            print(f"  {i}. [{video.bvid}] {video.title}")
        if len(videos) > 5:
            print(f"  ... 还有 {len(videos) - 5} 个视频")
        print()

        if not confirm:
            print("预览模式，使用 --confirm 确认删除")
            return

        # 确认删除
        print("=" * 60)
        print("开始删除...")
        print("=" * 60)

        # 删除文件
        deleted_files = 0

        for file_path in video_files:
            try:
                file_path.unlink()
                print(f"✓ 删除视频: {file_path}")
                deleted_files += 1
            except Exception as e:
                print(f"✗ 删除失败 {file_path}: {e}")

        for file_path in audio_files:
            try:
                file_path.unlink()
                print(f"✓ 删除音频: {file_path}")
                deleted_files += 1
            except Exception as e:
                print(f"✗ 删除失败 {file_path}: {e}")

        for file_path in text_files:
            try:
                file_path.unlink()
                print(f"✓ 删除文本: {file_path}")
                deleted_files += 1
            except Exception as e:
                print(f"✗ 删除失败 {file_path}: {e}")

        for file_path in markdown_files:
            try:
                file_path.unlink()
                print(f"✓ 删除Markdown: {file_path}")
                deleted_files += 1
            except Exception as e:
                print(f"✗ 删除失败 {file_path}: {e}")

        # 删除数据库记录
        for video in videos:
            db.delete(video)

        db.commit()

        print()
        print("=" * 60)
        print("✓ 清理完成！")
        print(f"  删除文件: {deleted_files} 个")
        print(f"  删除记录: {len(videos)} 条")
        print("=" * 60)

    except Exception as e:
        logger.error("清理失败: %s", e, exc_info=True)
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="清理指定 UP主的所有视频数据")
    parser.add_argument("mid", help="UP主 ID")
    parser.add_argument("--confirm", action="store_true", help="确认删除（不确认则只预览）")

    args = parser.parse_args()

    clear_uploader_videos(args.mid, args.confirm)
