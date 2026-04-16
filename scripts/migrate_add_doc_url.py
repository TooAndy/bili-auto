#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库迁移：为 videos 表添加 doc_url 字段
"""

import sys
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def migrate():
    """执行迁移"""
    db_path = Path(__file__).parent.parent / "data" / "bili.db"

    if not db_path.exists():
        print(f"[ERROR] 数据库文件不存在: {db_path}")
        return 1

    conn = None
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # 检查列是否已存在
        cursor.execute("PRAGMA table_info(videos)")
        columns = [col[1] for col in cursor.fetchall()]

        if "doc_url" in columns:
            print("[INFO] doc_url 列已存在，跳过迁移")
            return 0

        # 添加新列
        print("[INFO] 正在添加 doc_url 列...")
        cursor.execute("ALTER TABLE videos ADD COLUMN doc_url VARCHAR")
        conn.commit()

        print("[SUCCESS] 迁移完成！")
        return 0

    except Exception as e:
        print(f"[ERROR] 迁移失败: {e}")
        if conn:
            conn.rollback()
        return 1
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    sys.exit(migrate())
