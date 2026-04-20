"""
测试 paths.py - 路径管理模块
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile
import os

from app.utils.paths import (
    _sanitize_dirname,
    _sanitize_filename,
    PathManager,
    get_path_manager,
)


class TestSanitizeDirname:
    """测试目录名清理"""

    def test_remove_windows_invalid_chars(self):
        """测试：移除 Windows 不允许的字符"""
        assert _sanitize_dirname("视频:标题?") == "视频标题"
        assert _sanitize_dirname("a<b>c") == "abc"
        assert _sanitize_dirname('a"b|c') == "abc"

    def test_replace_slashes(self):
        """测试：斜杠替换为减号"""
        assert _sanitize_dirname("a/b\\c") == "a-b-c"

    def test_spaces_to_underscores(self):
        """测试：空格替换为下划线"""
        assert _sanitize_dirname("hello world") == "hello_world"

    def test_strip_leading_trailing(self):
        """测试：移除首尾点和下划线"""
        assert _sanitize_dirname("..hello..") == "hello"
        assert _sanitize_dirname("_test_") == "test"

    def test_truncate_long_name(self):
        """测试：超长名称被截断"""
        long_name = "a" * 100
        result = _sanitize_dirname(long_name, max_length=50)
        assert len(result) <= 50
        # 应该从最后一个下划线处截断
        assert "_" not in result or result.count("a") < 100

    def test_normal_name_unchanged(self):
        """测试：正常名称保持不变"""
        assert _sanitize_dirname("正常名称") == "正常名称"


class TestSanitizeFilename:
    """测试文件名清理"""

    def test_calls_sanitize_dirname(self):
        """测试：复用 _sanitize_dirname 逻辑"""
        assert _sanitize_filename("hello/world") == "hello-world"


class TestPathManager:
    """测试 PathManager"""

    def test_init_with_default(self):
        """测试：默认 data_root"""
        pm = PathManager()
        assert pm.data_root.name == "data"

    def test_init_with_custom_root(self):
        """测试：自定义 data_root"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PathManager(data_root=tmpdir)
            assert pm.data_root == Path(tmpdir)

    def test_get_uploader_dir_basic(self):
        """测试：获取 UP 主目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PathManager(data_root=tmpdir)
            uploader_dir = pm.get_uploader_dir("呆咪", "12345")
            assert uploader_dir.exists()
            assert "呆咪" in str(uploader_dir)

    def test_get_uploader_dir_without_mid(self):
        """测试：没有 MID 时目录名只有 UP 主名"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PathManager(data_root=tmpdir)
            uploader_dir = pm.get_uploader_dir("呆咪")
            assert uploader_dir.exists()

    def test_get_video_dir(self):
        """测试：获取视频目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PathManager(data_root=tmpdir)
            video_dir = pm.get_video_dir("呆咪", "BV123", "测试视频", pub_time=1712000000)
            assert video_dir.exists()
            assert "BV123" in str(video_dir)

    def test_get_video_dir_no_pub_time(self):
        """测试：无发布时间时使用 unknown"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PathManager(data_root=tmpdir)
            video_dir = pm.get_video_dir("呆咪", "BV123", "测试视频")
            assert video_dir.exists()
            assert "unknown" in str(video_dir)

    def test_get_video_paths(self):
        """测试：获取视频所有路径"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PathManager(data_root=tmpdir)
            paths = pm.get_video_paths("呆咪", "BV123", "测试视频", pub_time=1712000000)
            assert "dir" in paths
            assert "video" in paths
            assert "audio" in paths
            assert "transcript" in paths
            assert "summary" in paths
            assert paths["video"].suffix == ".mp4"
            assert paths["audio"].suffix == ".m4a"

    def test_get_dynamic_dir(self):
        """测试：获取动态目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PathManager(data_root=tmpdir)
            dyn_dir = pm.get_dynamic_dir("呆咪", "123456")
            assert dyn_dir.exists()
            assert "dynamics" in str(dyn_dir)

    def test_get_dynamic_paths(self):
        """测试：获取动态所有路径"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PathManager(data_root=tmpdir)
            paths = pm.get_dynamic_paths("呆咪", "123456")
            assert "dir" in paths
            assert "text" in paths
            assert "images" in paths

    def test_find_video_dir_by_bvid_not_exists(self):
        """测试：找不到视频目录返回 None"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PathManager(data_root=tmpdir)
            result = pm.find_video_dir_by_bvid("BV_nonexistent")
            assert result is None

    def test_find_video_dir_by_bvid_found(self):
        """测试：通过 BVID 找到视频目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PathManager(data_root=tmpdir)
            # 创建符合 PathManager 结构的目录
            video_dir = pm.get_video_dir("呆咪", "BV123", "测试视频", pub_time=1712000000)

            result = pm.find_video_dir_by_bvid("BV123")
            assert result is not None
            assert "BV123" in result.name

    def test_find_uploader_dir_by_mid_not_exists(self):
        """测试：找不到 UP 主目录返回 None"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PathManager(data_root=tmpdir)
            result = pm.find_uploader_dir_by_mid("nonexistent")
            assert result is None

    def test_find_uploader_dir_by_mid_found(self):
        """测试：通过 MID 找到 UP 主目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PathManager(data_root=tmpdir)
            # 通过 get_uploader_dir 创建目录结构
            uploader_dir = pm.get_uploader_dir("呆咪", "12345")

            result = pm.find_uploader_dir_by_mid("12345")
            assert result is not None
            assert result.name == "呆咪_12345"


class TestGetPathManager:
    """测试全局路径管理器"""

    def test_returns_singleton(self):
        """测试：返回单例"""
        # 清除全局实例
        import app.utils.paths as paths_module
        paths_module._default_manager = None

        with patch.object(paths_module, 'PathManager') as mock_pm_cls:
            mock_pm_cls.return_value = MagicMock()
            result1 = get_path_manager()
            result2 = get_path_manager()
            assert result1 is result2
