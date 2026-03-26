#!/usr/bin/env python3
"""
测试统一处理模块（纠错 + 总结）
"""
import sys
import json
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.modules.processor import process_text


def main():
    text_path = project_root / "data/text/BV1BaQBBiEHn.txt"
    raw_text = text_path.read_text("utf-8")

    print("=" * 60)
    print("测试统一处理模块（纠错 + 总结）")
    print("=" * 60)
    print(f"文本文件: {text_path}")
    print(f"原始文本长度: {len(raw_text)} 字符")
    print()

    try:
        result = process_text(
            raw_text=raw_text,
            video_title="海底捞财报解读",
            duration=0
        )

        print("✓ 处理成功!")
        print()
        print("=" * 60)
        print("处理结果:")
        print("=" * 60)
        print()
        print(f"纠正后文本长度: {len(result['corrected_text'])}")
        print()
        print("=" * 60)
        print("总结数据:")
        print("=" * 60)
        print(json.dumps({
            "summary": result["summary"],
            "key_points": result["key_points"],
            "tags": result["tags"],
            "insights": result["insights"]
        }, ensure_ascii=False, indent=2))
        print()

    except Exception as e:
        print(f"✗ 处理异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()