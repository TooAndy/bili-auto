#!/usr/bin/env python3
"""
根据数据库信息重命名已下载的文件
"""
import sys
import os
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.models.database import get_db, Video
from app.modules.downloader import _generate_filename


def rename_files():
    db = get_db()
    try:
        videos = db.query(Video).all()
        print(f"数据库中共有 {len(videos)} 个视频记录\n")

        renamed_count = 0
        for video in videos:
            bvid = video.bvid
            title = video.title
            pub_time = video.pub_time

            # 重命名视频
            if video.video_path:
                old_path = Path(video.video_path)
                if old_path.exists():
                    new_name = _generate_filename(bvid, title, pub_time, "mp4")
                    new_path = old_path.parent / new_name
                    try:
                        old_path.rename(new_path)
                        video.video_path = str(new_path)
                        print(f"✓ 视频: {new_name}")
                        renamed_count += 1
                    except Exception as e:
                        print(f"✗ 视频: {e}")

            # 重命名音频
            if video.audio_path:
                old_path = Path(video.audio_path)
                if old_path.exists():
                    new_name = _generate_filename(bvid, title, pub_time, "m4a")
                    new_path = old_path.parent / new_name
                    try:
                        old_path.rename(new_path)
                        video.audio_path = str(new_path)
                        print(f"✓ 音频: {new_name}")
                        renamed_count += 1
                    except Exception as e:
                        print(f"✗ 音频: {e}")

            # 重命名文本
            old_text = Path("data/text") / f"{bvid}.txt"
            if old_text.exists():
                new_name = _generate_filename(bvid, title, pub_time, "txt")
                new_path = old_text.parent / new_name
                try:
                    old_text.rename(new_path)
                    print(f"✓ 文本: {new_name}")
                    renamed_count += 1
                except Exception as e:
                    print(f"✗ 文本: {e}")

            # 重命名 Markdown
            old_md = Path("data/markdown") / f"{bvid}.md"
            if old_md.exists():
                new_name = _generate_filename(bvid, title, pub_time, "md")
                new_path = old_md.parent / new_name
                try:
                    old_md.rename(new_path)
                    print(f"✓ Markdown: {new_name}")
                    renamed_count += 1
                except Exception as e:
                    print(f"✗ Markdown: {e}")

        db.commit()
        print(f"\n完成！重命名了 {renamed_count} 个文件")
    finally:
        db.close()


if __name__ == "__main__":
    rename_files()
