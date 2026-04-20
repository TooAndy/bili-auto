#!/usr/bin/env python3
"""
测试 prompt 效果的脚本
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.modules.processor import process_text, _load_process_prompt


def main():
    # 测试文件路径
    transcript_path = project_root / "data" / "uploaders" / "呆咪_322005137" / "videos" / "20260331_BV1afXrBBEy7_第1154日投资记录：3月爆亏结束，保利财报还不错" / "transcript.txt"

    print("=" * 80)
    print("测试 Prompt 效果")
    print("=" * 80)

    # 1. 显示加载的 prompt
    print("\n[1/4] 加载的 Prompt:")
    print("-" * 80)
    prompt = _load_process_prompt()
    print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
    print(f"\n(总长度: {len(prompt)} 字符)")

    # 2. 读取转录文本
    print("\n[2/4] 读取转录文本:")
    print("-" * 80)
    if not transcript_path.exists():
        print(f"❌ 文件不存在: {transcript_path}")
        return

    with open(transcript_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    print(f"✓ 读取成功，长度: {len(raw_text)} 字符")
    print(f"\n前 300 字符:\n{raw_text[:300]}...")

    # 3. 调用处理
    print("\n[3/4] 调用 LLM 处理...")
    print("-" * 80)

    result = process_text(
        raw_text=raw_text,
        video_title="第1154日投资记录：3月爆亏结束，保利财报还不错",
        duration=0
    )

    # 4. 显示结果
    print("\n[4/4] 处理结果:")
    print("=" * 80)

    if not result.get("success"):
        print("❌ 处理失败")
        return

    print("✓ 处理成功!\n")

    print("【Summary】")
    print(result.get("summary", ""))
    with open(project_root / "test_output.md", "w", encoding="utf-8") as f:
        f.write(result.get("details", ""))
    print()

    print("【Key Points】")
    for i, point in enumerate(result.get("key_points", []), 1):
        print(f"{i}. {point}")
    print()

    print("【Stocks】")
    stocks = result.get("stocks", [])
    if stocks:
        for stock in stocks:
            print(f"• {stock}")
    else:
        print("(无)")
    print()

    print("【Insights】")
    print(result.get("insights", ""))
    print()

    print("【Details】")
    details = result.get("details", "")
    print(details[:500] + "..." if len(details) > 500 else details)
    print()

    print("=" * 80)
    print("测试完成!")
    print("=" * 80)


if __name__ == "__main__":
    main()
