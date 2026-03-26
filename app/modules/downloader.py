import subprocess
from pathlib import Path
from app.utils.logger import get_logger

logger = get_logger("downloader")


def download_audio(bvid: str, output_dir: str = "data/audio") -> str:
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    output_template = str(outdir / f"{bvid}.wav")

    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format",
        "wav",
        "--audio-quality",
        "192k",
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
