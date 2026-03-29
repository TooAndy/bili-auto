#!/usr/bin/env python3
"""
批量下载 UP 主视频工具

支持下载所有视频或按日期范围过滤，自动添加到数据库并处理
"""
import sys
import argparse
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.modules.bilibili import fetch_all_videos
from app.modules.downloader import download_video, QUALITY_FORMATS, DEFAULT_QUALITY
from app.models.database import get_db, Video
from app.utils.logger import get_logger

logger = get_logger("batch_download")


def parse_date(date_str: str) -> int:
    """
    解析日期字符串 (YYYYMMDD) 为 Unix 时间戳

    Args:
        date_str: 日期字符串，格式为 YYYYMMDD

    Returns:
        Unix 时间戳
    """
    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
        return int(dt.timestamp())
    except ValueError:
        raise argparse.ArgumentTypeError(f"无效的日期格式: {date_str}，应为 YYYYMMDD")


def preview_videos(videos: list, mid: str):
    """预览视频列表"""
    print(f"\n{'='*80}")
    print(f"UP 主 {mid} 的视频列表 (共 {len(videos)} 个)")
    print(f"{'='*80}\n")

    for i, video in enumerate(videos, 1):
        pub_time = datetime.fromtimestamp(video["pubdate"]).strftime("%Y-%m-%d %H:%M")
        print(f"{i:3d}. [{video['bvid']}] {video['title']}")
        print(f"     发布: {pub_time} | 时长: {video['duration']} | 播放: {video['play']}")
        print()


def add_videos_to_db(videos: list, mid: str, quality: str, force: bool = False):
    """添加视频到数据库"""
    db = get_db()
    try:
        added_count = 0
        skipped_count = 0
        updated_count = 0

        print(f"\n{'='*80}")
        print(f"添加视频到数据库 (清晰度: {quality})")
        print(f"{'='*80}\n")

        for video in videos:
            bvid = video["bvid"]
            title = video["title"]

            # 检查是否已存在
            existing = db.query(Video).filter_by(bvid=bvid).first()

            if existing:
                if force:
                    # 强制重新处理
                    print(f"[更新] {bvid} | {title}")
                    existing.status = "pending"
                    existing.attempt_count = 0
                    existing.last_error = None
                    updated_count += 1
                else:
                    # 跳过已存在的
                    print(f"[跳过] {bvid} | {title} (已存在)")
                    skipped_count += 1
                    continue
            else:
                # 添加新视频
                print(f"[添加] {bvid} | {title}")
                new_video = Video(
                    bvid=bvid,
                    title=title,
                    mid=mid,
                    pub_time=video["pubdate"],
                    status="pending"
                )
                db.add(new_video)
                added_count += 1

            # 下载视频
            try:
                print(f"      ↓ 下载视频 (清晰度: {quality})...")
                video_path = download_video(bvid, quality=quality)

                # 更新视频路径
                vid_obj = db.query(Video).filter_by(bvid=bvid).first()
                if vid_obj:
                    vid_obj.has_video = True
                    vid_obj.video_path = video_path

                print(f"      ✓ 下载完成: {video_path}")
            except Exception as e:
                print(f"      ✗ 下载失败: {e}")
                # 继续处理，不中断

        db.commit()

        print(f"\n{'='*80}")
        print(f"完成！新增: {added_count}, 更新: {updated_count}, 跳过: {skipped_count}")
        print(f"{'='*80}\n")
        print("提示: 视频已添加到数据库，queue_worker 将自动处理")

    except Exception as e:
        logger.error("添加视频失败: %s", e, exc_info=True)
        db.rollback()
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="批量下载 UP 主视频并添加到处理队列",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 获取 UP主 所有视频
  %(prog)s 1988098633 --all

  # 获取指定日期范围的视频
  %(prog)s 1988098633 --start-date 20250101 --end-date 20250331

  # 预览模式（不下载）
  %(prog)s 1988098633 --all --preview

  # 指定清晰度
  %(prog)s 1988098633 --all --quality 1080p

  # 强制重新处理已存在的视频
  %(prog)s 1988098633 --all --force
        """
    )

    parser.add_argument("mid", help="UP 主 ID")

    # 获取范围
    range_group = parser.add_mutually_exclusive_group(required=True)
    range_group.add_argument("--all", action="store_true", help="获取所有视频")
    range_group.add_argument("--start-date", type=parse_date, help="开始日期 (YYYYMMDD)")

    parser.add_argument("--end-date", type=parse_date, help="结束日期 (YYYYMMDD)")

    # 清晰度选项
    quality_choices = list(QUALITY_FORMATS.keys())
    parser.add_argument(
        "--quality",
        choices=quality_choices,
        default=DEFAULT_QUALITY,
        help=f"视频清晰度 (默认: {DEFAULT_QUALITY})"
    )

    # 其他选项
    parser.add_argument("--preview", action="store_true", help="预览模式，仅列出视频不下载")
    parser.add_argument("--force", action="store_true", help="强制重新处理已存在的视频")

    args = parser.parse_args()

    # 获取视频列表
    print(f"\n正在获取 UP 主 {args.mid} 的视频列表...")

    videos = fetch_all_videos(
        mid=args.mid,
        start_date=args.start_date,
        end_date=args.end_date
    )

    if not videos:
        print("未找到符合条件的视频")
        return

    # 预览模式
    if args.preview:
        preview_videos(videos, args.mid)
        return

    # 确认
    print(f"\n将下载 {len(videos)} 个视频 (清晰度: {args.quality})")
    if args.force:
        print("注意: 已存在的视频将被重新处理")

    confirm = input("\n确认继续? (y/n): ").strip().lower()
    if confirm != 'y':
        print("已取消")
        return

    # 添加到数据库并下载
    add_videos_to_db(videos, args.mid, args.quality, args.force)


if __name__ == "__main__":
    main()
