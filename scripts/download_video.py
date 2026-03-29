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
import time
from pathlib import Path
from datetime import datetime
from functools import wraps

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.modules.bilibili import fetch_all_videos, fetch_channel_videos
from app.modules.downloader import download_video
from app.models.database import get_db, Video
from app.utils.logger import get_logger

logger = get_logger("download_video")


def retry_on_db_lock(max_retries=3, delay=0.5):
    """数据库锁定重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if "database is locked" in str(e) and attempt < max_retries - 1:
                        logger.warning("数据库锁定，第%d次重试", attempt + 1)
                        time.sleep(delay * (attempt + 1))
                    else:
                        raise
        return wrapper
    return decorator


def safe_commit(db):
    """安全的数据库提交，带重试机制"""
    retry_on_db_lock()(db.commit)()


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

            # 2. 检查数据库和视频文件
            existing = db.query(Video).filter_by(bvid=bvid).first()

            # 检查视频文件是否真实存在
            has_video_file = False
            if existing and existing.video_path:
                # 优先使用数据库中的路径
                video_file = Path(existing.video_path)
                has_video_file = video_file.exists()
            if not has_video_file:
                # 如果数据库路径无效，搜索目录下是否有该 bvid 的文件
                video_dir = Path("data/video")
                if video_dir.exists():
                    for f in video_dir.glob(f"*{bvid}*.mp4"):
                        has_video_file = True
                        break

            if existing:
                if force or not existing.has_video or not has_video_file:
                    # 强制重新下载 或 视频文件缺失
                    if not has_video_file:
                        print(f"[续传] 视频文件缺失，重新下载")
                    else:
                        print(f"[更新] 强制重新下载")
                    existing.status = "pending"
                    existing.attempt_count = 0
                    existing.last_error = None
                else:
                    print(f"[跳过] 视频已存在且已下载")
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
                safe_commit(db)  # 立即提交，让 queue_worker 能看到

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

                safe_commit(db)
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

            # 检查数据库和视频文件
            existing = db.query(Video).filter_by(bvid=bvid).first()

            # 检查视频文件是否真实存在
            has_video_file = False
            if existing and existing.video_path:
                # 优先使用数据库中的路径
                video_file = Path(existing.video_path)
                has_video_file = video_file.exists()
            if not has_video_file:
                # 如果数据库路径无效，搜索目录下是否有该 bvid 的文件
                video_dir = Path("data/video")
                if video_dir.exists():
                    for f in video_dir.glob(f"*{bvid}*.mp4"):
                        has_video_file = True
                        break

            if existing:
                if force or not existing.has_video or not has_video_file:
                    # 强制重新下载 或 视频文件缺失
                    if not has_video_file:
                        print(f"[续传] {bvid} | 视频文件缺失")
                    else:
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
                safe_commit(db)  # 立即提交，让 queue_worker 能看到

            # 下载视频
            try:
                actual_video_path = download_video(
                    bvid,
                    quality=quality,
                    title=title,
                    pub_time=pubdate
                )

                # 更新数据库（使用实际返回的路径）
                vid_obj = db.query(Video).filter_by(bvid=bvid).first()
                if vid_obj:
                    vid_obj.has_video = True
                    vid_obj.video_path = actual_video_path

                safe_commit(db)  # 立即提交更新
                print(f"  ✓ 下载完成")

            except Exception as e:
                logger.error("下载失败 %s: %s", bvid, e)
                print(f"  ✗ 下载失败: {e}")

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
  # 下载单个视频 (BV 开头自动识别)
  %(prog)s BV1C8ZiBDEdx

  # 批量下载 UP主所有视频 (纯数字自动识别)
  %(prog)s 1988098633 --all

  # 批量下载指定日期范围
  %(prog)s 1988098633 --start-date 20250101 --end-date 20250331

  # 下载多个视频
  %(prog)s BV1C8ZiBDEdx BV1iz6pBxEmV

  # 指定清晰度
  %(prog)s BV1C8ZiBDEdx --quality 1080p

  # 强制重新下载
  %(prog)s BV1C8ZiBDEdx --force
        """
    )

    # 主参数（视频ID或UP主ID）
    parser.add_argument("ids", nargs="+", help="视频 ID (BV开头) 或 UP 主 ID (纯数字)")

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

    # 自动识别模式
    has_batch_flag = args.all or args.start_date or args.end_date

    if has_batch_flag:
        # 批量下载模式：需要 UP 主 ID
        if len(args.ids) != 1:
            parser.error("批量下载模式需要指定一个 UP 主 ID（纯数字）")

        mid = args.ids[0]
        if not mid.isdigit():
            parser.error(f"UP 主 ID 应该是纯数字，但得到: {mid}")

        print(f"批量下载模式: UP 主 {mid}")
        if args.all:
            print("  范围: 所有视频")
        else:
            print(f"  范围: {args.start_date} - {args.end_date}")

        download_batch(mid, args.start_date, args.end_date, args.quality, args.force)

    else:
        # 单视频下载模式：支持多个视频 ID
        bvids = []
        for id_str in args.ids:
            if id_str.startswith("BV"):
                bvids.append(id_str)
            elif id_str.isdigit():
                print(f"警告: {id_str} 看起来像 UP 主 ID，但没有使用 --all 参数")
                print(f"  如果要批量下载，请使用: {sys.argv[0]} {id_str} --all")
                continue
            else:
                print(f"警告: 无法识别 ID 类型: {id_str}")

        if not bvids:
            parser.error("没有找到有效的视频 ID (应以 BV 开头)")

        print(f"单视频下载模式: {len(bvids)} 个视频")
        download_single_videos(bvids, args.quality, args.force)


if __name__ == "__main__":
    main()
