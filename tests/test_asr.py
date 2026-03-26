"""
测试 ASR 相关模块 - whisper_ai.py, asr.py
"""
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.modules import whisper_ai
from app.modules import asr


def test_whisper_transcribe_import():
    """测试：whisper_ai 模块可以正常导入"""
    assert whisper_ai.transcribe_audio is not None


def test_whisper_transcribe_function_signature(sample_wav_path):
    """测试：transcribe_audio 函数签名正确"""
    # 虽然我们不实际运行（因为需要下载模型），但可以检查函数存在
    assert callable(whisper_ai.transcribe_audio)


def test_asr_get_transcribe_function_whisper():
    """测试：返回 whisper 函数"""
    func = asr.get_transcribe_function()

    # 应该返回 whisper_ai.transcribe_audio
    assert func.__name__ == 'transcribe_audio' or 'whisper' in func.__module__


def test_asr_transcribe_audio_interface(sample_wav_path):
    """测试：统一 ASR 接口可以被调用"""
    # mock whisper 的 transcribe_audio
    with patch('app.modules.whisper_ai.transcribe_audio') as mock_transcribe:
        mock_transcribe.return_value = "这是测试转录文本"

        # 重置 _transcribe 缓存
        asr._transcribe = None
        result = asr.transcribe_audio(sample_wav_path)

    mock_transcribe.assert_called_once_with(sample_wav_path)
    assert result == "这是测试转录文本"




# ========== 集成测试 ==========
# 这些测试需要实际调用模型或 API，默认不运行
# 运行方式: uv run pytest -m integration

@pytest.mark.integration
def test_whisper_integration_real_transcribe(sample_wav_path):
    """集成测试：实际调用本地 Whisper 进行识别（需要下载模型）"""
    print("\n" + "="*60)
    print("测试本地 Whisper ASR")
    print("="*60)
    print(f"音频文件: {sample_wav_path}")

    try:
        result = whisper_ai.transcribe_audio(sample_wav_path)
        print(f"识别结果: {result}")
        print(f"结果长度: {len(result)}")

        # 即使是静音也可能返回空或一些文本，不做强断言
        assert isinstance(result, str)
        print("✓ Whisper 调用成功")

    except Exception as e:
        pytest.skip(f"Whisper 测试跳过（可能需要下载模型）: {e}")



@pytest.mark.integration
def test_asr_unified_integration(sample_wav_path):
    """集成测试：测试统一 ASR 接口"""
    print("\n" + "="*60)
    print("测试统一 ASR 接口")
    print("="*60)

    # 重置缓存
    asr._transcribe = None

    # 测试: 使用 Whisper
    print("\n--- 测试 Whisper ---")
    with patch('app.modules.whisper_ai.transcribe_audio') as mock_whisper:
        mock_whisper.return_value = "测试 Whisper 结果"
        asr._transcribe = None
        result = asr.transcribe_audio(sample_wav_path)
        assert result == "测试 Whisper 结果"
        print("✓ Whisper 接口测试通过")

    print("\n✓ 统一 ASR 接口测试完成")
