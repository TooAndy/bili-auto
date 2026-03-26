#!/usr/bin/env python3
"""
测试 Dashscope ASR 的各种调用方式
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config
from app.utils.logger import get_logger

logger = get_logger("test_asr")

print("=" * 60)
print("测试 Dashscope ASR")
print("=" * 60)

print("\n1. 检查配置...")
print(f"   ASR_PROVIDER: {Config.ASR_PROVIDER}")
print(f"   ASR_API_KEY: {Config.ASR_API_KEY[:10] if Config.ASR_API_KEY else 'None'}...")
print(f"   ASR_BASE_URL: {Config.ASR_BASE_URL}")
print(f"   ASR_MODEL: {Config.ASR_MODEL}")

print("\n2. 尝试导入 dashscope...")
try:
    import dashscope
    from dashscope.audio.asr import Transcription
    print("   ✓ dashscope 导入成功")

    # 配置
    if Config.ASR_API_KEY:
        dashscope.api_key = Config.ASR_API_KEY
        dashscope.base_http_api_url = Config.ASR_BASE_URL
        print("   ✓ dashscope 配置成功")
    else:
        print("   ✗ ASR_API_KEY 未设置")
        sys.exit(1)

except ImportError as e:
    print(f"   ✗ dashscope 导入失败: {e}")
    print("   请运行: uv add dashscope")
    sys.exit(1)
except Exception as e:
    print(f"   ✗ dashscope 初始化失败: {e}")
    sys.exit(1)

print("\n3. 检查 Transcription API...")
import inspect
print(f"   async_call 签名: {inspect.signature(Transcription.async_call)}")

print("\n4. 尝试查找一个音频文件...")
audio_dir = Path("data/audio")
audio_files = list(audio_dir.glob("*.wav")) if audio_dir.exists() else []

if audio_files:
    print(f"   找到 {len(audio_files)} 个音频文件")
    test_audio = str(audio_files[0])
    print(f"   测试文件: {test_audio}")

    print("\n5. 尝试调用 ASR (使用 file_urls)...")
    try:
        # 方式1: 直接文件路径
        print("\n   方式1: 直接文件路径")
        task_response = Transcription.async_call(
            model=Config.ASR_MODEL,
            file_urls=[test_audio],
            language_hints=["zh", "en"]
        )
        print(f"   ✓ 任务提交成功: {task_response}")

    except Exception as e:
        print(f"   ✗ 方式1失败: {type(e).__name__}: {e}")

    try:
        # 方式2: file:// URL
        print("\n   方式2: file:// URL")
        audio_url = f"file://{os.path.abspath(test_audio)}"
        print(f"   URL: {audio_url}")
        task_response = Transcription.async_call(
            model=Config.ASR_MODEL,
            file_urls=[audio_url],
            language_hints=["zh", "en"]
        )
        print(f"   ✓ 任务提交成功: {task_response}")

    except Exception as e:
        print(f"   ✗ 方式2失败: {type(e).__name__}: {e}")

else:
    print("   未找到音频文件，请先下载一个音频进行测试")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
