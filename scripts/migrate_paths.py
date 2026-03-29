#!/usr/bin/env python3
"""
数据迁移脚本
将旧的文件结构迁移到新的按 UP 主组织的结构
"""
import sys
import shutil
from pathlib import Path
from typing import Dict, Optional, Tuple

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.models.database import get_db, Video, Subscription
from app.utils.paths import PathManager, get_path_manager
from app.utils.logger import get_logger

logger = get_logger("migrate_paths")


def get_uploader_info(db, mid: str) -> Tuple[Optional[str], Optional[str]]:
    """
    从数据库获取 UP 主信息

    Args:
        db: 数据库会话
        mid: UP 主 MID

    Returns:
        (name, mid) 元组
    """
    sub = db.query(Subscription).filter_by(mid=mid).first()
    if sub:
        return sub.name, sub.mid
    return None, mid


def find_old_files(data_root: Path, bvid: str) -> Dict[str, Optional[Path]]:
    """
    在旧目录结构中查找视频相关文件

    Args:
        data_root: 数据根目录
        bvid: 视频 BVID

    Returns:
        文件路径字典
    """
    result = {
        "video": None,
        "audio": None,
        "text": None,
        "markdown": None,
    }

    # 查找视频文件
    video_dir = data_root / "video"
    if video_dir.exists():
        for f in video_dir.glob(f"*{bvid}*"):
            if f.suffix in [".mp4", ".mkv", ".flv"]:
                result["video"] = f
                break

    # 查找音频文件
    audio_dir = data_root / "audio"
    if audio_dir.exists():
        for f in audio_dir.glob(f"*{bvid}*"):
            if f.suffix in [".m4a", ".wav", ".mp3"]:
                result["audio"] = f
                break

    # 查找文本文件
    text_dir = data_root / "text"
    if text_dir.exists():
        for f in text_dir.glob(f"*{bvid}*"):
            if f.suffix == ".txt":
                result["text"] = f
                break

    # 查找 Markdown 文件
    markdown_dir = data_root / "markdown"
    if markdown_dir.exists():
        for f in markdown_dir.glob(f"*{bvid}*"):
            if f.suffix == ".md":
                result["markdown"] = f
                break

    return result


def migrate_video(
    pm: PathManager,
    video: Video,
    uploader_name: str,
    uploader_mid: str,
    data_root: Path
) -> bool:
    """
    迁移单个视频

    Args:
        pm: 路径管理器
        video: 视频对象
        uploader_name: UP 主名称
        uploader_mid: UP 主 MID
        data_root: 数据根目录

    Returns:
        是否成功
    """
    logger.info(f"迁移视频: {video.bvid} | {video.title}")

    # 检查是否已经迁移过
    existing_dir = pm.find_video_dir_by_bvid(video.bvid)
    if existing_dir:
        logger.info(f"  跳过: 视频已存在于 {existing_dir}")
        return True

    # 查找旧文件
    old_files = find_old_files(data_root, video.bvid)

    # 获取新路径
    new_paths = pm.get_video_paths(
        uploader_name=uploader_name,
        bvid=video.bvid,
        title=video.title,
        pub_time=video.pub_time,
        uploader_mid=uploader_mid
    )

    migrated_count = 0

    # 迁移视频文件
    if old_files["video"]:
        try:
            # 使用新的固定名称 video.mp4
            shutil.copy2(old_files["video"], new_paths["video"])
            logger.info(f"  ✓ 视频: {old_files['video'].name} -> video.mp4")
            migrated_count += 1

            # 更新数据库路径
            video.video_path = str(new_paths["video"].relative_to(project_root))
        except Exception as e:
            logger.error(f"  ✗ 视频迁移失败: {e}")

    # 迁移音频文件
    if old_files["audio"]:
        try:
            # 使用新的固定名称 audio.m4a
            shutil.copy2(old_files["audio"], new_paths["audio"])
            logger.info(f"  ✓ 音频: {old_files['audio'].name} -> audio.m4a")
            migrated_count += 1

            # 更新数据库路径
            video.audio_path = str(new_paths["audio"].relative_to(project_root))
        except Exception as e:
            logger.error(f"  ✗ 音频迁移失败: {e}")

    # 迁移文本文件
    if old_files["text"]:
        try:
            # 使用新的固定名称 transcript.txt
            shutil.copy2(old_files["text"], new_paths["transcript"])
            logger.info(f"  ✓ 文本: {old_files['text'].name} -> transcript.txt")
            migrated_count += 1
        except Exception as e:
            logger.error(f"  ✗ 文本迁移失败: {e}")

    # 迁移 Markdown 文件
    if old_files["markdown"]:
        try:
            # 使用新的固定名称 summary.md
            shutil.copy2(old_files["markdown"], new_paths["summary"])
            logger.info(f"  ✓ 总结: {old_files['markdown'].name} -> summary.md")
            migrated_count += 1
        except Exception as e:
            logger.error(f"  ✗ 总结迁移失败: {e}")

    if migrated_count > 0:
        logger.info(f"  完成: 迁移了 {migrated_count} 个文件到 {new_paths['dir']}")
        return True
    else:
        # 即使没有文件，也创建目录结构
        new_paths["dir"].mkdir(parents=True, exist_ok=True)
        logger.info(f"  完成: 创建目录结构 {new_paths['dir']}")
        return True


def main():
    """主迁移函数"""
    print("=" * 60)
    print("数据迁移工具")
    print("=" * 60)
    print()

    data_root = project_root / "data"
    pm = get_path_manager()
    db = get_db()

    try:
        # 获取所有视频
        videos = db.query(Video).order_by(Video.created_at.desc()).all()
        print(f"找到 {len(videos)} 个视频\n")

        success_count = 0
        fail_count = 0

        for video in videos:
            # 获取 UP 主信息
            uploader_name, uploader_mid = get_uploader_info(db, video.mid)
            if not uploader_name:
                uploader_name = f"UP主_{video.mid}"

            # 迁移视频
            try:
                ok = migrate_video(pm, video, uploader_name, uploader_mid, data_root)
                if ok:
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                logger.error(f"迁移视频 {video.bvid} 时出错: {e}", exc_info=True)
                fail_count += 1

            print()

        # 提交数据库更新
        db.commit()

        print("=" * 60)
        print(f"迁移完成!")
        print(f"  成功: {success_count}")
        print(f"  失败: {fail_count}")
        print("=" * 60)
        print()
        print("注意: 原文件仍然保留在旧目录中，确认无误后可手动删除。")
        print(f"旧目录: {data_root}/video, {data_root}/audio, {data_root}/text, {data_root}/markdown")

    except KeyboardInterrupt:
        print("\n\n用户中断，已停止迁移")
        db.rollback()
    except Exception as e:
        logger.error(f"迁移过程出错: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
