#!/usr/bin/env python3
"""
测试 ASR 语音识别
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.modules.whisper_ai import transcribe_audio


def main():
    audio_path = project_root / "data/audio/BV1BaQBBiEHn.wav"

    print("=" * 60)
    print("测试 ASR 语音识别")
    print("=" * 60)
    print(f"音频文件: {audio_path}")
    print(f"文件大小: {audio_path.stat().st_size / 1024 / 1024:.2f} MB")
    print()

    try:
        print("开始识别...")
        result = transcribe_audio(str(audio_path))

        print()
        print("=" * 60)
        print("识别结果:")
        print("=" * 60)
        print(result)
        print()
        print(f"总长度: {len(result)} 字符")
        print("✓ 识别成功!")

    except Exception as e:
        print(f"✗ 识别失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()