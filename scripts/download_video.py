#!/usr/bin/env python3
"""
视频下载工具 - 支持单视频和批量下载

功能：
- 单视频下载：指定 BV 号下载
- 批量下载：下载 UP主所有视频或指定日期范围
- 自动处理：下载后 queue_worker 自动处理（提取音频→识别→总结）
"""
import sys
import argparse
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.modules.bilibili import fetch_all_videos, fetch_channel_videos
from app.modules.downloader import download_video
from app.models.database import get_db, Video
from app.utils.logger import get_logger

logger = get_logger("download_video")


def get_video_info(bvid: str) -> dict:
    """获取单个视频的详细信息"""
    import requests
    from config import Config

    url = "https://api.bilibili.com/x/web-interface/view"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.bilibili.com",
    }
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


def download_single_videos(bvids: list, quality: str, force: bool):
    """下载单个或多个视频"""
    db = get_db()
    try:
        for i, bvid in enumerate(bvids, 1):
            print(f"\n[{i}/{len(bvids)}] 处理: {bvid}")
            print("-" * 50)

            # 1. 获取视频信息
            print(f"正在获取视频信息...")
            video_info = get_video_info(bvid)

            if not video_info:
                print(f"❌ 无法获取视频信息: {bvid}")
                continue

            title = video_info["title"]
            pub_time = video_info["pubdate"]
            mid = video_info["mid"]

            print(f"  标题: {title}")
            print(f"  UP主: {video_info['owner']}")
            print(f"  时长: {video_info['duration']}")

            # 2. 检查数据库
            existing = db.query(Video).filter_by(bvid=bvid).first()

            if existing:
                if force:
                    print(f"[更新] 强制重新下载")
                    existing.status = "pending"
                    existing.attempt_count = 0
                    existing.last_error = None
                else:
                    print(f"[跳过] 视频已存在")
                    continue
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

            # 3. 下载视频
            try:
                print(f"开始下载视频 (清晰度: {quality})...")
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
                print(f"✓ 下载完成: {Path(video_path).name}")

            except Exception as e:
                logger.error("下载失败: %s", e)
                print(f"❌ 下载失败: {e}")

        print(f"\n{'='*50}")
        print("下载完成！queue_worker 将自动处理视频")
        print(f"{'='*50}")

    except Exception as e:
        logger.error("处理失败: %s", e, exc_info=True)
        db.rollback()
    finally:
        db.close()


def download_batch(mid: str, start_date: int = None, end_date: int = None,
                   quality: str = "high", force: bool = False):
    """批量下载 UP主视频"""
    db = get_db()
    try:
        # 获取视频列表
        print(f"正在获取 UP主 {mid} 的视频列表...")
        videos = fetch_all_videos(
            mid=mid,
            start_date=start_date,
            end_date=end_date
        )

        if not videos:
            print("未找到符合条件的视频")
            return

        print(f"找到 {len(videos)} 个视频\n")

        # 批量处理
        added_count = 0
        updated_count = 0
        skipped_count = 0

        for video in videos:
            bvid = video["bvid"]
            title = video["title"]
            pubdate = video.get("pubdate", 0)

            # 检查数据库
            existing = db.query(Video).filter_by(bvid=bvid).first()

            if existing:
                if force:
                    print(f"[更新] {bvid} | {title[:50]}...")
                    existing.status = "pending"
                    existing.attempt_count = 0
                    existing.last_error = None
                    updated_count += 1
                else:
                    print(f"[跳过] {bvid} | {title[:50]}...")
                    skipped_count += 1
                    continue
            else:
                print(f"[添加] {bvid} | {title[:50]}...")
                new_video = Video(
                    bvid=bvid,
                    title=title,
                    mid=str(mid),
                    pub_time=pubdate,
                    status="pending"
                )
                db.add(new_video)
                added_count += 1

            # 下载视频
            try:
                download_video(
                    bvid,
                    quality=quality,
                    title=title,
                    pub_time=pubdate
                )

                # 更新数据库
                vid_obj = db.query(Video).filter_by(bvid=bvid).first()
                if vid_obj:
                    vid_obj.has_video = True
                    vid_obj.video_path = str(Path("data/video") / f"{bvid}.mp4")

                print(f"  ✓ 下载完成")

            except Exception as e:
                logger.error("下载失败 %s: %s", bvid, e)
                print(f"  ✗ 下载失败: {e}")

        db.commit()

        print(f"\n{'='*50}")
        print(f"完成！新增: {added_count}, 更新: {updated_count}, 跳过: {skipped_count}")
        print(f"{'='*50}")
        print("提示: queue_worker 将自动处理视频")

    except Exception as e:
        logger.error("批量下载失败: %s", e, exc_info=True)
        db.rollback()
    finally:
        db.close()


def parse_date(date_str: str) -> int:
    """解析日期字符串 (YYYYMMDD) 为 Unix 时间戳"""
    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
        return int(dt.timestamp())
    except ValueError:
        raise argparse.ArgumentTypeError(f"无效的日期格式: {date_str}，应为 YYYYMMDD")


def main():
    parser = argparse.ArgumentParser(
        description="视频下载工具 - 支持单视频和批量下载",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 下载单个视频
  %(prog)s BV1C8ZiBDEdx

  # 下载多个视频
  %(prog)s BV1C8ZiBDEdx BV1iz6pBxEmV

  # 批量下载 UP主所有视频
  %(prog)s 1988098633 --all

  # 批量下载指定日期范围
  %(prog)s 1988098633 --start-date 20250101 --end-date 20250331

  # 指定清晰度
  %(prog)s BV1C8ZiBDEdx --quality 1080p

  # 强制重新下载
  %(prog)s BV1C8ZiBDEdx --force
        """
    )

    # 视频 ID（位置参数）
    parser.add_argument("ids", nargs="*", help="视频 ID (BV号) 或 UP主 ID")

    # 批量下载选项
    parser.add_argument("--all", action="store_true", help="批量下载：下载 UP主所有视频")
    parser.add_argument("--start-date", type=parse_date, help="批量下载：开始日期 (YYYYMMDD)")
    parser.add_argument("--end-date", type=parse_date, help="批量下载：结束日期 (YYYYMMDD)")

    # 通用选项
    parser.add_argument("--quality", "-q",
                       choices=["4k", "high", "1080p", "720p", "480p", "360p"],
                       default="high",
                       help="视频清晰度（默认: high）")
    parser.add_argument("--force", "-f", action="store_true",
                       help="强制重新下载已存在的视频")
    parser.add_argument("--yes", "-y", action="store_true",
                       help="批量下载时跳过确认")

    args = parser.parse_args()

    # 判断模式
    if args.all or args.start_date:
        # 批量下载模式
        if not args.ids or len(args.ids) != 1:
            parser.error("批量下载模式需要指定一个 UP 主 ID")

        mid = args.ids[0]
        print(f"批量下载模式: UP 主 {mid}")
        if args.all:
            print("  范围: 所有视频")
        else:
            print(f"  范围: {args.start_date} - {args.end_date}")

        download_batch(mid, args.start_date, args.end_date, args.quality, args.force)

    elif args.ids:
        # 单视频下载模式
        bvids = args.ids
        print(f"单视频下载模式: {len(bvids)} 个视频")
        download_single_videos(bvids, args.quality, args.force)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
