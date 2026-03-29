import subprocess
import os
import tempfile
import re
from datetime import datetime
from pathlib import Path
from app.utils.logger import get_logger
from config import Config

logger = get_logger("downloader")

# 视频清晰度映射到 yt-dlp 格式选择器
QUALITY_FORMATS = {
    "4k": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
    "high": "bestvideo+bestaudio/best",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
}

DEFAULT_QUALITY = "high"


def _sanitize_filename(title: str, max_length: int = 50) -> str:
    """
    清理文件名，移除或替换特殊字符

    Args:
        title: 原始标题
        max_length: 最大长度（超过则截断）

    Returns:
        清理后的文件名
    """
    # 移除或替换特殊字符
    title = re.sub(r'[<>:"|?*]', '', title)  # Windows 不允许的字符
    title = re.sub(r'[\\/]', '-', title)       # 斜杠改为减号
    title = re.sub(r'\s+', '_', title)         # 空格改为下划线
    title = title.strip('._')                  # 移除首尾的点和下划线

    # 截断过长的标题
    if len(title) > max_length:
        title = title[:max_length].rsplit('_', 1)[0]  # 在下划线处截断

    return title


def _generate_filename(bvid: str, title: str, pub_time: int = None, ext: str = "mp4") -> str:
    """
    生成文件名：日期_BVID_标题.ext

    Args:
        bvid: 视频 ID
        title: 视频标题
        pub_time: 发布时间（Unix timestamp）
        ext: 文件扩展名

    Returns:
        生成的文件名
    """
    # 处理发布时间
    if pub_time:
        date_str = datetime.fromtimestamp(pub_time).strftime("%Y%m%d")
    else:
        date_str = "unknown"

    # 清理标题
    clean_title = _sanitize_filename(title)

    # 组合文件名
    filename = f"{date_str}_{bvid}_{clean_title}.{ext}"

    return filename


def _get_ytdlp_cookies_args() -> list:
    """
    获取 yt-dlp 的 Cookie 参数

    Returns:
        yt-dlp 命令行参数列表
    """
    if not Config.BILIBILI_COOKIE:
        return []

    # 将 Cookie 字符串写入临时文件（Netscape 格式）
    import tempfile

    # 创建临时 cookie 文件
    cookie_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    cookie_path = cookie_file.name

    try:
        # 简化的 Netscape cookie 格式
        # B站主要域名是 .bilibili.com
        cookie_file.write("# Netscape HTTP Cookie File\n")
        cookie_file.write("# This is a generated file! Do not edit.\n\n")

        # 解析 Cookie 字符串
        for part in Config.BILIBILI_COOKIE.split(';'):
            part = part.strip()
            if '=' in part:
                name, value = part.split('=', 1)
                cookie_file.write(f".bilibili.com\tTRUE\t/\tTRUE\t0\t{name}\t{value}\n")

        cookie_file.close()
        return ["--cookies", cookie_path]
    except Exception as e:
        logger.error("创建 Cookie 文件失败: %s", e)
        return []


def download_audio(bvid: str, output_dir: str = "data/audio", title: str = None, pub_time: int = None) -> str:
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    # 生成文件名（新格式）
    if title and pub_time:
        filename = _generate_filename(bvid, title, pub_time, "m4a")
    else:
        filename = f"{bvid}.m4a"

    output_path = outdir / filename

    # 检查文件是否已存在
    if output_path.exists():
        logger.info("音频文件已存在，跳过下载: %s", output_path)
        return str(output_path)

    # 也检查一下旧的 wav/mp3 文件是否存在
    for ext in [".wav", ".mp3"]:
        old_path = outdir / f"{bvid}{ext}"
        if old_path.exists():
            logger.info("发现旧的 %s 文件，直接使用: %s", ext, old_path)
            return str(old_path)

    output_template = str(output_path)
    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format",
        "m4a",
        "--audio-quality",
        "128k",
        "-o",
        output_template,
        *_get_ytdlp_cookies_args(),
        f"https://www.bilibili.com/video/{bvid}"
    ]

    logger.info("开始下载音频: %s", bvid)

    # 清理临时 Cookie 文件
    cookie_file = None
    if len(cmd) > 8 and cmd[8] == "--cookies":
        cookie_file = Path(cmd[9])

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)

        if proc.returncode != 0:
            logger.error("yt-dlp 下载失败: %s", proc.stderr)
            raise RuntimeError(f"下载失败: {proc.stderr}")

        logger.info("下载完成: %s", output_template)
        return output_template
    finally:
        # 清理临时 Cookie 文件
        if cookie_file and cookie_file.exists():
            try:
                cookie_file.unlink()
            except:
                pass


def download_video(bvid: str, quality: str = DEFAULT_QUALITY, output_dir: str = "data/video", title: str = None, pub_time: int = None) -> str:
    """
    下载 B站视频

    会员视频需要配置 BILIBILI_COOKIE 才能下载完整版

    Args:
        bvid: 视频 ID
        quality: 清晰度，可选: 4k, high, 1080p, 720p, 480p, 360p，默认 high
        output_dir: 输出目录
        title: 视频标题（用于生成文件名）
        pub_time: 发布时间（用于生成文件名）

    Returns:
        视频文件路径
    """
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    # 生成文件名（新格式）
    if title and pub_time:
        filename = _generate_filename(bvid, title, pub_time, "mp4")
    else:
        filename = f"{bvid}.mp4"

    output_path = outdir / filename

    # 检查文件是否已存在
    if output_path.exists():
        logger.info("视频文件已存在，跳过下载: %s", output_path)
        return str(output_path)

    # 检查 Cookie 配置
    if not Config.BILIBILI_COOKIE:
        logger.warning("未配置 BILIBILI_COOKIE，会员视频只能下载试看片段")

    # 获取格式选择器
    format_selector = QUALITY_FORMATS.get(quality.lower(), QUALITY_FORMATS[DEFAULT_QUALITY])
    logger.debug("使用清晰度: %s (格式: %s)", quality, format_selector)

    output_template = str(output_path)
    cmd = [
        "yt-dlp",
        "-f", format_selector,
        "--merge-output-format", "mp4",
        "-o", output_template,
        *_get_ytdlp_cookies_args(),
        f"https://www.bilibili.com/video/{bvid}"
    ]

    logger.info("开始下载视频: %s (清晰度: %s)", bvid, quality)

    # 清理临时 Cookie 文件
    cookie_file = None
    if len(cmd) > 9 and cmd[9] == "--cookies":
        cookie_file = Path(cmd[10])

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)

        if proc.returncode != 0:
            logger.error("yt-dlp 下载视频失败: %s", proc.stderr)
            raise RuntimeError(f"下载视频失败: {proc.stderr}")

        logger.info("视频下载完成: %s", output_template)
        return output_template
    finally:
        # 清理临时 Cookie 文件
        if cookie_file and cookie_file.exists():
            try:
                cookie_file.unlink()
            except:
                pass


def extract_audio_from_video(video_path: str) -> str:
    """
    从视频文件提取音频（保存为临时 wav 文件）

    Args:
        video_path: 视频文件路径

    Returns:
        临时音频文件路径（wav 格式）
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"视频文件不存在: {video_path}")

    # 创建临时文件
    with tempfile.NamedTemporaryFile(prefix="video_audio_", suffix=".wav", delete=False) as f:
        temp_audio = Path(f.name)

    # 使用 ffmpeg 提取音频
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(video_path),
        "-vn",  # 不处理视频流
        "-ar", "16000",  # 采样率 16kHz（whisper 推荐）
        "-ac", "1",  # 单声道
        "-c:a", "pcm_s16le",  # PCM 16位小端
        str(temp_audio)
    ]

    logger.debug("提取音频: %s → %s", video_path, temp_audio)
    proc = subprocess.run(cmd, capture_output=True, text=True)

    if proc.returncode != 0:
        logger.error("ffmpeg 提取音频失败: %s", proc.stderr)
        raise RuntimeError(f"提取音频失败: {proc.stderr}")

    logger.info("音频提取完成: %s", temp_audio)
    return str(temp_audio)
