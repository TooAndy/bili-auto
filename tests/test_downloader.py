"""
测试 downloader.py - 音频下载模块
"""
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.modules import downloader


def test_download_audio_skip_existing(temp_dir, sample_wav_path):
    """测试：如果文件已存在，跳过下载"""
    # 先创建一个"已存在"的文件
    bvid = "BV1234567890"
    output_path = temp_dir / f"{bvid}.wav"

    # 把测试文件复制过去
    import shutil
    shutil.copy(sample_wav_path, output_path)

    with patch('subprocess.run') as mock_run:
        result = downloader.download_audio(bvid, output_dir=str(temp_dir))

        # 验证 subprocess.run 没有被调用
        mock_run.assert_not_called()

        # 验证返回的是已存在的文件
        assert result == str(output_path)
        assert os.path.exists(result)


def test_download_audio_calls_yt_dlp(temp_dir, mock_subprocess):
    """测试：调用 yt-dlp 下载音频"""
    bvid = "BV1234567890"
    output_path = temp_dir / f"{bvid}.wav"

    # 确保文件不存在（这样才会调用下载）
    assert not output_path.exists()

    # mock subprocess.run，在调用后创建文件
    def mock_run(cmd, **kwargs):
        # 模拟 yt-dlp 下载成功后创建文件
        output_path.touch()
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""
        return result

    mock_subprocess.side_effect = mock_run

    result = downloader.download_audio(bvid, output_dir=str(temp_dir))

    # 验证调用了 subprocess.run
    mock_subprocess.assert_called_once()
    cmd_args = mock_subprocess.call_args[0][0]

    # 验证命令包含必要参数
    assert "yt-dlp" in cmd_args
    assert "-x" in cmd_args
    assert "--audio-format" in cmd_args
    assert "m4a" in cmd_args
    assert bvid in cmd_args[-1]


def test_download_audio_failure_raises_error(temp_dir, mock_subprocess):
    """测试：下载失败时抛出异常"""
    bvid = "BV1234567890"
    output_path = temp_dir / f"{bvid}.wav"

    # 确保文件不存在（这样才会尝试下载）
    assert not output_path.exists()

    # 模拟 yt-dlp 失败
    mock_subprocess.return_value.returncode = 1
    mock_subprocess.return_value.stderr = "Download failed"

    with pytest.raises(RuntimeError) as exc_info:
        downloader.download_audio(bvid, output_dir=str(temp_dir))

    assert "下载失败" in str(exc_info.value)


def test_download_audio_creates_output_dir(temp_dir):
    """测试：自动创建输出目录"""
    bvid = "BV1234567890"
    nested_dir = temp_dir / "nested" / "path" / "to" / "audio"
    output_path = nested_dir / f"{bvid}.wav"

    # 确保目录不存在
    assert not nested_dir.exists()

    # 先创建文件（模拟已下载），这样会跳过 subprocess.run 调用
    nested_dir.mkdir(parents=True, exist_ok=True)
    output_path.touch()

    result = downloader.download_audio(bvid, output_dir=str(nested_dir))

    # 验证目录存在
    assert nested_dir.exists()
    assert os.path.isdir(nested_dir)
