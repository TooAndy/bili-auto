"""
pytest fixtures for tests
"""
import os
import sys
import tempfile
import wave
import struct
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def temp_dir():
    """临时目录 fixture"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_wav_path(temp_dir):
    """创建一个简单的测试用 WAV 文件"""
    wav_path = temp_dir / "test.wav"

    # 创建一个简单的 WAV 文件（1秒的静音）
    sample_rate = 16000
    duration = 1  # 秒
    num_samples = sample_rate * duration

    with wave.open(str(wav_path), 'w') as wav_file:
        wav_file.setnchannels(1)  # 单声道
        wav_file.setsampwidth(2)  # 2字节/样本 (16位)
        wav_file.setframerate(sample_rate)

        # 写入静音数据
        for _ in range(num_samples):
            wav_file.writeframes(struct.pack('<h', 0))

    return str(wav_path)


@pytest.fixture
def mock_config():
    """mock Config fixture"""
    with patch('config.Config') as mock_cfg:
        mock_cfg.ASR_PROVIDER = 'whisper'
        mock_cfg.ASR_API_KEY = ''
        mock_cfg.ASR_BASE_URL = ''
        mock_cfg.ASR_MODEL = 'fun-asr'
        yield mock_cfg


@pytest.fixture
def mock_subprocess():
    """mock subprocess.run fixture"""
    with patch('subprocess.run') as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ''
        mock_result.stderr = ''
        mock_run.return_value = mock_result
        yield mock_run
