import subprocess
import os
from pathlib import Path
from app.utils.logger import get_logger

logger = get_logger("downloader")


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
