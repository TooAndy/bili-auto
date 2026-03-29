#!/usr/bin/env python3
"""
下载指定视频编号的视频，并自动处理

功能：
1. 获取视频信息（标题、发布时间等）
2. 下载完整视频
3. 添加到数据库
4. queue_worker 自动处理（提取音频→识别→生成摘要）
"""
import sys
import argparse
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.modules.bilibili import fetch_channel_videos
from app.modules.downloader import download_video
from app.models.database import get_db, Video
from app.utils.logger import get_logger

logger = get_logger("download_video")


def get_video_info(bvid: str) -> dict:
    """
    获取单个视频的详细信息

    Args:
        bvid: 视频 ID

    Returns:
        视频信息字典，如果失败返回 None
    """
    import requests

    url = "https://api.bilibili.com/x/web-interface/view"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.bilibili.com",
    }
    from config import Config
    if Config.BILIBILI_COOKIE:
        headers["Cookie"] = Config.BILIBILI_COOKIE

    try:
        resp = requests.get(url, params={"bvid": bvid}, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            logger.error("获取视频信息失败: %s", data.get("message"))
            return None

        view_data = data.get("data", {})
        return {
            "bvid": bvid,
            "title": view_data.get("title"),
            "pubdate": view_data.get("pubdate"),
            "duration": view_data.get("duration"),
            "pic": view_data.get("pic"),
            "description": view_data.get("desc", ""),
            "owner": view_data.get("owner", {}).get("name", ""),
            "mid": view_data.get("owner", {}).get("mid", ""),
        }
    except Exception as e:
        logger.error("获取视频信息异常: %s", e)
        return None


def download_single_video(bvid: str, quality: str = "high", force: bool = False):
    """
    下载单个视频并添加到数据库

    Args:
        bvid: 视频 ID
        quality: 视频清晰度
        force: 是否强制重新下载
    """
    db = get_db()
    try:
        # 1. 获取视频信息
        print(f"正在获取视频信息: {bvid}")
        video_info = get_video_info(bvid)

        if not video_info:
            print(f"❌ 无法获取视频信息: {bvid}")
            return

        title = video_info["title"]
        pub_time = video_info["pubdate"]
        mid = video_info["mid"]
        duration = video_info["duration"]

        print(f"  标题: {title}")
        print(f"  UP主: {video_info['owner']}")
        print(f"  发布时间: {pub_time}")
        print(f"  时长: {duration}")
        print()

        # 2. 检查数据库
        existing = db.query(Video).filter_by(bvid=bvid).first()

        if existing:
            if force:
                print(f"[更新] 视频已存在，强制重新下载")
                existing.status = "pending"
                existing.attempt_count = 0
                existing.last_error = None
            else:
                print(f"[跳过] 视频已存在，使用 --force 重新下载")
                return
        else:
            print(f"[添加] 新视频")
            new_video = Video(
                bvid=bvid,
                title=title,
                mid=str(mid),
                pub_time=pub_time,
                status="pending"
            )
            db.add(new_video)
            db.commit()

        # 3. 下载视频
        print(f"开始下载视频 (清晰度: {quality})...")
        try:
            video_path = download_video(
                bvid,
                quality=quality,
                title=title,
                pub_time=pub_time
            )

            # 更新数据库
            vid_obj = db.query(Video).filter_by(bvid=bvid).first()
            if vid_obj:
                vid_obj.has_video = True
                vid_obj.video_path = video_path

            db.commit()

            print(f"✓ 下载完成: {video_path}")
            print()
            print("="*60)
            print("视频已添加到数据库")
            print("queue_worker 将自动处理:")
            print("  1. 提取音频")
            print("  2. 语音识别 (Whisper)")
            print("  3. LLM 纠错+总结")
            print("  4. 保存文本和 Markdown")
            print("="*60)

        except Exception as e:
            logger.error("下载失败: %s", e)
            print(f"❌ 下载失败: {e}")
            db.rollback()

    except Exception as e:
        logger.error("处理失败: %s", e, exc_info=True)
        db.rollback()
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="下载指定视频并自动处理",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 下载单个视频
  %(prog)s BV1C8ZiBDEdx

  # 指定清晰度
  %(prog)s BV1C8ZiBDEdx --quality 1080p

  # 强制重新下载已存在的视频
  %(prog)s BV1C8ZiBDEdx --force

  # 下载多个视频
  %(prog)s BV1C8ZiBDEdx BV1iz6pBxEmV BV1x3zWB6EU6
        """
    )

    parser.add_argument("bvid", nargs="+", help="视频 ID（BV号），支持多个")
    parser.add_argument("--quality", "-q",
                       choices=["4k", "high", "1080p", "720p", "480p", "360p"],
                       default="high",
                       help="视频清晰度（默认: high）")
    parser.add_argument("--force", "-f", action="store_true",
                       help="强制重新下载已存在的视频")

    args = parser.parse_args()

    bvids = args.bvid

    print(f"将下载 {len(bvids)} 个视频\n")

    for i, bvid in enumerate(bvids, 1):
        print(f"\n[{i}/{len(bvids)}] 处理: {bvid}")
        print("-" * 60)
        download_single_video(bvid, args.quality, args.force)


if __name__ == "__main__":
    main()
