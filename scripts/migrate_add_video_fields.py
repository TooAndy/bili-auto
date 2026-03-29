#!/usr/bin/env python3
"""
数据库迁移脚本：添加视频相关字段

添加字段：
- has_video: 是否成功下载视频
- video_path: 视频文件路径
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import sqlite3
from config import Config


def migrate():
    """执行数据库迁移"""
    db_path = Config.DATABASE_URL.replace("sqlite:///", "")

    print(f"数据库路径: {db_path}")
    print()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 检查字段是否已存在
        cursor.execute("PRAGMA table_info(videos)")
        columns = [col[1] for col in cursor.fetchall()]

        if "has_video" in columns and "video_path" in columns:
            print("✓ 字段已存在，无需迁移")
            return

        print("=" * 60)
        print("数据库迁移：添加视频相关字段")
        print("=" * 60)
        print()

        # 添加 has_video 字段
        if "has_video" not in columns:
            print("添加字段: has_video")
            cursor.execute("ALTER TABLE videos ADD COLUMN has_video BOOLEAN DEFAULT 0")
        else:
            print("字段已存在: has_video")

        # 添加 video_path 字段
        if "video_path" not in columns:
            print("添加字段: video_path")
            cursor.execute("ALTER TABLE videos ADD COLUMN video_path VARCHAR")
        else:
            print("字段已存在: video_path")

        conn.commit()
        print()
        print("✓ 迁移完成！")

    except Exception as e:
        print(f"✗ 迁移失败: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
