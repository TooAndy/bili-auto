"""
路径管理模块
统一管理所有文件路径，按 UP 主 + 视频组织
"""
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple


def _sanitize_dirname(name: str, max_length: int = 50) -> str:
    """
    清理目录名，移除或替换特殊字符

    Args:
        name: 原始名称
        max_length: 最大长度

    Returns:
        清理后的目录名
    """
    # 移除或替换特殊字符
    name = re.sub(r'[<>:"|?*]', '', name)  # Windows 不允许的字符
    name = re.sub(r'[\\/]', '-', name)       # 斜杠改为减号
    name = re.sub(r'\s+', '_', name)         # 空格改为下划线
    name = name.strip('._')                  # 移除首尾的点和下划线

    # 截断过长的名称
    if len(name) > max_length:
        name = name[:max_length].rsplit('_', 1)[0]

    return name


def _sanitize_filename(title: str, max_length: int = 50) -> str:
    """
    清理文件名，移除或替换特殊字符

    Args:
        title: 原始标题
        max_length: 最大长度

    Returns:
        清理后的文件名
    """
    return _sanitize_dirname(title, max_length)


class PathManager:
    """路径管理器"""

    def __init__(self, data_root: str = None):
        """
        初始化路径管理器

        Args:
            data_root: 数据根目录，默认为项目根目录下的 data
        """
        if data_root is None:
            # 默认使用项目根目录下的 data
            data_root = Path(__file__).resolve().parent.parent.parent / "data"

        self.data_root = Path(data_root)
        self.uploaders_dir = self.data_root / "uploaders"

        # 确保根目录存在
        self.uploaders_dir.mkdir(parents=True, exist_ok=True)

    def get_uploader_dir(self, uploader_name: str, uploader_mid: str = None) -> Path:
        """
        获取 UP 主目录

        Args:
            uploader_name: UP 主名称
            uploader_mid: UP 主 MID（可选，用于避免重名）

        Returns:
            UP 主目录路径
        """
        # 清理 UP 主名称
        clean_name = _sanitize_dirname(uploader_name)

        # 如果有 MID，加入到目录名中避免重名
        if uploader_mid:
            dir_name = f"{clean_name}_{uploader_mid}"
        else:
            dir_name = clean_name

        uploader_dir = self.uploaders_dir / dir_name
        uploader_dir.mkdir(parents=True, exist_ok=True)
        return uploader_dir

    def get_video_dir(
        self,
        uploader_name: str,
        bvid: str,
        title: str,
        pub_time: int = None,
        uploader_mid: str = None
    ) -> Path:
        """
        获取视频目录

        Args:
            uploader_name: UP 主名称
            bvid: 视频 BVID
            title: 视频标题
            pub_time: 发布时间戳
            uploader_mid: UP 主 MID（可选）

        Returns:
            视频目录路径
        """
        uploader_dir = self.get_uploader_dir(uploader_name, uploader_mid)
        videos_dir = uploader_dir / "videos"
        videos_dir.mkdir(parents=True, exist_ok=True)

        # 处理发布时间
        if pub_time:
            date_str = datetime.fromtimestamp(pub_time).strftime("%Y%m%d")
        else:
            date_str = "unknown"

        # 清理标题
        clean_title = _sanitize_filename(title, max_length=40)

        # 视频目录名：日期_BVID_标题
        video_dir_name = f"{date_str}_{bvid}_{clean_title}"
        video_dir = videos_dir / video_dir_name
        video_dir.mkdir(parents=True, exist_ok=True)
        return video_dir

    def get_video_paths(
        self,
        uploader_name: str,
        bvid: str,
        title: str,
        pub_time: int = None,
        uploader_mid: str = None
    ) -> dict:
        """
        获取视频所有相关文件路径

        Args:
            uploader_name: UP 主名称
            bvid: 视频 BVID
            title: 视频标题
            pub_time: 发布时间戳
            uploader_mid: UP 主 MID（可选）

        Returns:
            包含所有路径的字典
        """
        video_dir = self.get_video_dir(uploader_name, bvid, title, pub_time, uploader_mid)

        return {
            "dir": video_dir,
            "video": video_dir / "video.mp4",
            "audio": video_dir / "audio.m4a",
            "transcript": video_dir / "transcript.txt",
            "summary": video_dir / "summary.md",
        }

    def get_dynamic_dir(
        self,
        uploader_name: str,
        dynamic_id: str,
        uploader_mid: str = None
    ) -> Path:
        """
        获取动态目录

        Args:
            uploader_name: UP 主名称
            dynamic_id: 动态 ID
            uploader_mid: UP 主 MID（可选）

        Returns:
            动态目录路径
        """
        uploader_dir = self.get_uploader_dir(uploader_name, uploader_mid)
        dynamics_dir = uploader_dir / "dynamics"
        dynamics_dir.mkdir(parents=True, exist_ok=True)

        dynamic_dir = dynamics_dir / dynamic_id
        dynamic_dir.mkdir(parents=True, exist_ok=True)
        return dynamic_dir

    def get_dynamic_paths(
        self,
        uploader_name: str,
        dynamic_id: str,
        uploader_mid: str = None
    ) -> dict:
        """
        获取动态所有相关文件路径

        Args:
            uploader_name: UP 主名称
            dynamic_id: 动态 ID
            uploader_mid: UP 主 MID（可选）

        Returns:
            包含所有路径的字典
        """
        dynamic_dir = self.get_dynamic_dir(uploader_name, dynamic_id, uploader_mid)
        images_dir = dynamic_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        return {
            "dir": dynamic_dir,
            "text": dynamic_dir / "text.txt",
            "images": images_dir,
        }

    def find_video_dir_by_bvid(self, bvid: str) -> Optional[Path]:
        """
        通过 BVID 查找视频目录

        Args:
            bvid: 视频 BVID

        Returns:
            视频目录路径，如果找不到返回 None
        """
        if not self.uploaders_dir.exists():
            return None

        # 遍历所有 UP 主目录
        for uploader_dir in self.uploaders_dir.iterdir():
            if not uploader_dir.is_dir():
                continue

            videos_dir = uploader_dir / "videos"
            if not videos_dir.exists():
                continue

            # 遍历该 UP 主的所有视频目录
            for video_dir in videos_dir.iterdir():
                if not video_dir.is_dir():
                    continue

                # 检查目录名是否包含 BVID
                if f"_{bvid}_" in video_dir.name or video_dir.name.endswith(f"_{bvid}"):
                    return video_dir

        return None

    def find_uploader_dir_by_mid(self, mid: str) -> Optional[Path]:
        """
        通过 MID 查找 UP 主目录

        Args:
            mid: UP 主 MID

        Returns:
            UP 主目录路径，如果找不到返回 None
        """
        if not self.uploaders_dir.exists():
            return None

        # 遍历所有 UP 主目录
        for uploader_dir in self.uploaders_dir.iterdir():
            if not uploader_dir.is_dir():
                continue

            # 检查目录名是否以 _{mid} 结尾
            if uploader_dir.name.endswith(f"_{mid}"):
                return uploader_dir

        return None


# 全局路径管理器实例
_default_manager: Optional[PathManager] = None


def get_path_manager() -> PathManager:
    """获取全局路径管理器实例"""
    global _default_manager
    if _default_manager is None:
        _default_manager = PathManager()
    return _default_manager
