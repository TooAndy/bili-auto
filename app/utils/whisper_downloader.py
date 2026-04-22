"""
whisper.cpp 自动下载工具
首次启动时检测并下载对应平台的 whisper.cpp CLI 和模型
"""
import hashlib
import os
import platform
from pathlib import Path

import requests
from app.utils.logger import get_logger

logger = get_logger("whisper_downloader")

RELEASES_API = "https://api.github.com/repos/ggerganov/whisper.cpp/releases/latest"
CLI_ASSETS = {
    "darwin-arm64": "whisper-bin-darwin-arm64",
    "darwin-x86_64": "whisper-bin-darwin-x86_64",
    "linux-x64": "whisper-bin-linux-x64",
}
MODEL_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin"

# ggml-small.bin SHA256 校验和（来自官方）
# 模型更新后此值会变化，可通过环境变量覆盖
GGML_SMALL_SHA256 = os.environ.get(
    "GGML_SMALL_SHA256",
    "55356645c2b361a969dfd0ef2c5a50d530afd8d5"
)

# 是否验证模型 SHA256（默认开启）
# 设为 false 可跳过校验，适用于模型更新后 hash 未更新的过渡期
VERIFY_MODEL_HASH = os.environ.get("VERIFY_MODEL_HASH", "true").lower() != "false"


def detect_platform() -> str:
    """检测当前平台和架构"""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "darwin":
        return "darwin-arm64" if machine == "arm64" else "darwin-x86_64"
    elif system == "linux":
        return "linux-x64"
    else:
        raise ValueError(f"Unsupported platform: {system}-{machine}")


def _get_cli_download_url() -> tuple[str, str]:
    """获取 CLI 下载 URL 和文件名"""
    plat = detect_platform()
    asset_name = CLI_ASSETS.get(plat)
    if not asset_name:
        raise ValueError(f"No prebuilt binary for {plat}")

    response = requests.get(RELEASES_API, timeout=30)
    response.raise_for_status()
    data = response.json()

    for asset in data.get("assets", []):
        if asset["name"] == asset_name:
            return asset["browser_download_url"], asset_name

    raise FileNotFoundError(f"Asset {asset_name} not found in releases")


def _download_with_progress(url: str, dest: Path, expected_sha256: str = None) -> bool:
    """
    下载文件，带进度显示和 SHA256 校验

    Args:
        url: 下载 URL
        dest: 目标文件路径
        expected_sha256: 期望的 SHA256（可选）

    Returns:
        是否下载成功
    """
    try:
        headers = {"User-Agent": "bili-auto/1.0"}
        response = requests.get(url, stream=True, headers=headers, timeout=600)
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))

        dest.parent.mkdir(parents=True, exist_ok=True)

        downloaded = 0
        sha256_hash = hashlib.sha256()
        with open(dest, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                sha256_hash.update(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded * 100 // total
                    print(f"\r  下载中: {pct}%", end="", flush=True)

        print()

        if expected_sha256 and VERIFY_MODEL_HASH:
            actual = sha256_hash.hexdigest()
            if actual != expected_sha256:
                logger.error(
                    "SHA256 mismatch: expected %s..., got %s...",
                    expected_sha256[:8],
                    actual[:8]
                )
                dest.unlink()
                return False
            logger.debug("SHA256 校验通过")
        elif not VERIFY_MODEL_HASH:
            logger.debug("SHA256 校验已跳过（VERIFY_MODEL_HASH=false）")

        return True
    except Exception as e:
        logger.warning(f"Download failed: {e}")
        if dest.exists():
            dest.unlink()
        return False


def ensure_whisper_cli(cli_path: str) -> bool:
    """确保 whisper.cpp CLI 存在"""
    if os.path.exists(cli_path):
        logger.debug(f"whisper.cpp CLI exists: {cli_path}")
        return True

    logger.info("Downloading whisper.cpp CLI...")
    try:
        url, filename = _get_cli_download_url()
        temp_path = Path(cli_path + ".tmp")
        if _download_with_progress(url, temp_path):
            temp_path.chmod(0o755)
            temp_path.rename(cli_path)
            logger.info(f"whisper.cpp CLI saved to {cli_path}")
            return True
    except Exception as e:
        logger.warning(f"Failed to download whisper.cpp: {e}")

    return False


def ensure_whisper_model(model_path: str) -> bool:
    """确保 whisper 模型存在（约 500MB）"""
    if os.path.exists(model_path):
        logger.debug(f"whisper model exists: {model_path}")
        return True

    logger.info("Downloading ggml-small.bin model (~500MB)...")
    try:
        temp_path = Path(model_path + ".tmp")
        if _download_with_progress(MODEL_URL, temp_path, GGML_SMALL_SHA256):
            temp_path.rename(model_path)
            logger.info(f"Model saved to {model_path}")
            return True
    except Exception as e:
        logger.warning(f"Failed to download model: {e}")

    return False


def setup_whisper() -> bool:
    """
    设置 whisper.cpp，返回是否成功（失败时回退到 faster-whisper）

    检查环境变量 WHISPER_CPP_CLI 和 WHISPER_CPP_MODEL，
    如果未设置则使用默认值 /app/models/whisper 和 /app/models/ggml-small.bin
    """
    cli_path = os.environ.get("WHISPER_CPP_CLI", "/app/models/whisper")
    model_path = os.environ.get("WHISPER_CPP_MODEL", "/app/models/ggml-small.bin")

    cli_ok = ensure_whisper_cli(cli_path)
    model_ok = ensure_whisper_model(model_path)

    if not cli_ok or not model_ok:
        logger.warning("whisper.cpp setup failed, will use faster-whisper instead")
        return False

    return True