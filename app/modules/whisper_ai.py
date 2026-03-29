import os
import subprocess
import tempfile
from pathlib import Path
from app.utils.logger import get_logger
from config import Config

logger = get_logger("whisper")

# 检查是否使用 whisper.cpp
USE_WHISPER_CPP = Config.USE_WHISPER_CPP

# Whisper.cpp 配置（如果启用）
WHISPER_CPP_CLI = None
WHISPER_CPP_MODEL = None

if USE_WHISPER_CPP:
    WHISPER_CPP_CLI = Path(Config.WHISPER_CPP_CLI) if Config.WHISPER_CPP_CLI else None
    WHISPER_CPP_MODEL = Path(Config.WHISPER_CPP_MODEL) if Config.WHISPER_CPP_MODEL else None

    # 验证配置
    if not WHISPER_CPP_CLI or not WHISPER_CPP_CLI.exists():
        logger.warning("WHISPER_CPP_CLI 配置无效或文件不存在，禁用 whisper.cpp")
        USE_WHISPER_CPP = False
    elif not WHISPER_CPP_MODEL or not WHISPER_CPP_MODEL.exists():
        logger.warning("WHISPER_CPP_MODEL 配置无效或文件不存在，禁用 whisper.cpp")
        USE_WHISPER_CPP = False

if USE_WHISPER_CPP:
    logger.info("使用 whisper.cpp 进行语音识别")
    logger.info("  CLI: %s", WHISPER_CPP_CLI)
    logger.info("  Model: %s", WHISPER_CPP_MODEL)
else:
    logger.info("使用 faster-whisper 进行语音识别")
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel(
            Config.WHISPER_MODEL,
            device=Config.WHISPER_DEVICE,
            compute_type="int8",
            download_root="models"
        )
    except ImportError:
        logger.warning("faster-whisper 未安装")
        model = None


def transcribe_audio(audio_path: str) -> str:
    """
    使用 Whisper 进行语音识别

    支持视频文件输入（自动提取音频）

    如果配置了 USE_WHISPER_CPP=true 且 whisper.cpp 可用，使用 whisper.cpp
    否则使用 faster-whisper
    """
    logger.info("Whisper 识别: %s", audio_path)

    # 检查是否是视频文件
    video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm']
    input_path = Path(audio_path)

    if input_path.suffix.lower() in video_extensions:
        logger.debug("检测到视频文件，先提取音频...")
        from app.modules.downloader import extract_audio_from_video
        temp_audio = extract_audio_from_video(str(input_path))
        logger.debug("临时音频文件: %s", temp_audio)

        try:
            if USE_WHISPER_CPP:
                result = _transcribe_with_cpp(temp_audio)
            else:
                result = _transcribe_with_faster_whisper(temp_audio)
        finally:
            # 清理临时文件
            try:
                Path(temp_audio).unlink()
                logger.debug("已清理临时音频文件")
            except:
                pass
        return result

    if USE_WHISPER_CPP:
        return _transcribe_with_cpp(audio_path)
    else:
        return _transcribe_with_faster_whisper(audio_path)


def _transcribe_with_cpp(audio_path: str) -> str:
    """使用 whisper.cpp 进行识别"""
    if not WHISPER_CPP_CLI.exists():
        raise RuntimeError(f"whisper-cli 不存在: {WHISPER_CPP_CLI}")
    if not WHISPER_CPP_MODEL.exists():
        raise RuntimeError(f"whisper 模型不存在: {WHISPER_CPP_MODEL}")

    input_path = Path(audio_path)
    temp_wav = None

    # 如果不是 wav 格式，先用 ffmpeg 转换
    if not input_path.suffix.lower() == ".wav":
        logger.debug("音频非 wav 格式，使用 ffmpeg 转换: %s", input_path.suffix)
        with tempfile.NamedTemporaryFile(prefix="whisper_input_", suffix=".wav", delete=False, dir="/tmp") as f:
            temp_wav = Path(f.name)

        # 使用 ffmpeg 转换
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-i", str(input_path),
            "-ar", "16000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            str(temp_wav)
        ]
        logger.debug("执行 ffmpeg 转换: %s", " ".join(ffmpeg_cmd))
        ffmpeg_proc = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        if ffmpeg_proc.returncode != 0:
            logger.error("ffmpeg 转换失败: %s", ffmpeg_proc.stderr)
            raise RuntimeError(f"ffmpeg 转换失败: {ffmpeg_proc.stderr}")

        input_for_whisper = str(temp_wav)
    else:
        input_for_whisper = str(input_path)

    # 使用随机文件名避免多进程冲突
    with tempfile.NamedTemporaryFile(prefix="whisper_out_", suffix="", delete=False, dir="/tmp") as f:
        output_prefix = f.name

    try:
        cmd = [
            str(WHISPER_CPP_CLI),
            "-m", str(WHISPER_CPP_MODEL),
            "-f", input_for_whisper,
            "-l", "zh",
            "--output-txt",  # 输出 txt 文件
            "--output-file", output_prefix  # 输出文件前缀
        ]

        logger.debug("执行命令: %s", " ".join(cmd))

        proc = subprocess.run(cmd, capture_output=True, text=True)

        if proc.returncode != 0:
            logger.error("whisper.cpp 失败: %s", proc.stderr)
            raise RuntimeError(f"whisper.cpp 识别失败: {proc.stderr}")

        # 读取输出文件
        output_file = Path(f"{output_prefix}.txt")
        if output_file.exists():
            text = output_file.read_text("utf-8").strip()
            # 清理输出文件
            try:
                output_file.unlink()
            except:
                pass
        else:
            # 如果没有输出文件，从 stdout 解析
            text = proc.stdout.strip()

        logger.info("whisper.cpp 完成，文本长度 %d", len(text))
        return text
    finally:
        # 清理临时文件（如果还存在）
        try:
            Path(output_prefix).unlink(missing_ok=True)
            Path(f"{output_prefix}.txt").unlink(missing_ok=True)
            if temp_wav:
                temp_wav.unlink(missing_ok=True)
        except:
            pass


def _transcribe_with_faster_whisper(audio_path: str) -> str:
    """使用 faster-whisper 进行识别"""
    if model is None:
        raise RuntimeError("faster-whisper 模型未初始化")

    segments, _ = model.transcribe(
        audio_path,
        language="zh",
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=True
    )
    text = "\n".join([segment.text for segment in segments])
    logger.info("faster-whisper 完成，文本长度 %d", len(text))
    return text
