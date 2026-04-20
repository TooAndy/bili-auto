"""
测试 downloader.py - 音频下载模块
"""
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.modules import downloader


class TestSanitizeFilename:
    """测试 _sanitize_filename 函数"""

    def test_remove_windows_invalid_chars(self):
        """测试：移除 Windows 不允许的字符"""
        assert downloader._sanitize_filename("视频:标题?") == "视频标题"
        assert downloader._sanitize_filename("a<b>c") == "abc"
        assert downloader._sanitize_filename('a"b|c') == "abc"

    def test_replace_slashes(self):
        """测试：斜杠替换为减号"""
        assert downloader._sanitize_filename("a/b\\c") == "a-b-c"

    def test_spaces_to_underscores(self):
        """测试：空格替换为下划线"""
        assert downloader._sanitize_filename("hello world") == "hello_world"

    def test_strip_leading_trailing(self):
        """测试：移除首尾的点和下划线"""
        assert downloader._sanitize_filename("..hello..") == "hello"
        assert downloader._sanitize_filename("_test_") == "test"

    def test_truncate_long_name(self):
        """测试：超长名称被截断"""
        long_name = "a" * 100
        result = downloader._sanitize_filename(long_name, max_length=50)
        assert len(result) <= 50

    def test_normal_name_unchanged(self):
        """测试：正常名称保持不变"""
        assert downloader._sanitize_filename("正常名称") == "正常名称"


class TestGenerateFilename:
    """测试 _generate_filename 函数"""

    def test_generate_with_pub_time(self):
        """测试：带发布时间生成文件名"""
        result = downloader._generate_filename("BV123", "测试标题", pub_time=1704067200)
        assert "20240101" in result
        assert "BV123" in result
        assert "测试标题" in result
        assert result.endswith(".mp4")

    def test_generate_without_pub_time(self):
        """测试：不带发布时间使用 unknown"""
        result = downloader._generate_filename("BV456", "标题")
        assert "unknown" in result
        assert "BV456" in result

    def test_generate_custom_ext(self):
        """测试：自定义扩展名"""
        result = downloader._generate_filename("BV123", "标题", ext="m4a")
        assert result.endswith(".m4a")


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
