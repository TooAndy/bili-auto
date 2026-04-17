#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库迁移：添加 classification_rules 和 folder_mappings 表
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

        # 检查 classification_rules 表是否已存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='classification_rules'")
        if cursor.fetchone():
            print("[INFO] classification_rules 表已存在")
        else:
            print("[INFO] 正在创建 classification_rules 表...")
            cursor.execute("""
                CREATE TABLE classification_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uploader_name VARCHAR NOT NULL,
                    pattern VARCHAR NOT NULL,
                    target_folder VARCHAR NOT NULL,
                    priority INTEGER DEFAULT 100,
                    is_active INTEGER DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("[SUCCESS] classification_rules 表创建完成")

        # 检查 folder_mappings 表是否已存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='folder_mappings'")
        if cursor.fetchone():
            print("[INFO] folder_mappings 表已存在")
        else:
            print("[INFO] 正在创建 folder_mappings 表...")
            cursor.execute("""
                CREATE TABLE folder_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uploader_name VARCHAR NOT NULL,
                    category VARCHAR NOT NULL,
                    folder_token VARCHAR NOT NULL,
                    folder_path VARCHAR UNIQUE NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("[SUCCESS] folder_mappings 表创建完成")

        conn.commit()
        print("[SUCCESS] 所有迁移完成！")
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