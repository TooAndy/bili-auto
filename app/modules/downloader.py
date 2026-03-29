import subprocess
import os
import tempfile
from pathlib import Path
from app.utils.logger import get_logger

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


def download_audio(bvid: str, output_dir: str = "data/audio") -> str:
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    output_path = outdir / f"{bvid}.m4a"

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
        f"https://www.bilibili.com/video/{bvid}"
    ]

    logger.info("开始下载音频: %s", bvid)
    proc = subprocess.run(cmd, capture_output=True, text=True)

    if proc.returncode != 0:
        logger.error("yt-dlp 下载失败: %s", proc.stderr)
        raise RuntimeError(f"下载失败: {proc.stderr}")

    logger.info("下载完成: %s", output_template)
    return output_template


def download_video(bvid: str, quality: str = DEFAULT_QUALITY, output_dir: str = "data/video") -> str:
    """
    下载 B站视频

    Args:
        bvid: 视频 ID
        quality: 清晰度，可选: 4k, high, 1080p, 720p, 480p, 360p，默认 high
        output_dir: 输出目录

    Returns:
        视频文件路径
    """
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    output_path = outdir / f"{bvid}.mp4"

    # 检查文件是否已存在
    if output_path.exists():
        logger.info("视频文件已存在，跳过下载: %s", output_path)
        return str(output_path)

    # 获取格式选择器
    format_selector = QUALITY_FORMATS.get(quality.lower(), QUALITY_FORMATS[DEFAULT_QUALITY])
    logger.debug("使用清晰度: %s (格式: %s)", quality, format_selector)

    output_template = str(output_path)
    cmd = [
        "yt-dlp",
        "-f", format_selector,
        "--merge-output-format", "mp4",
        "-o", output_template,
        f"https://www.bilibili.com/video/{bvid}"
    ]

    logger.info("开始下载视频: %s (清晰度: %s)", bvid, quality)
    proc = subprocess.run(cmd, capture_output=True, text=True)

    if proc.returncode != 0:
        logger.error("yt-dlp 下载视频失败: %s", proc.stderr)
        raise RuntimeError(f"下载视频失败: {proc.stderr}")

    logger.info("视频下载完成: %s", output_template)
    return output_template


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
