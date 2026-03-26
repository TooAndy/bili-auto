"""
统一的 ASR 语音识别接口
使用 Whisper 进行语音识别
"""
from app.utils.logger import get_logger

logger = get_logger("asr")


def get_transcribe_function():
    """
    获取语音识别函数

    Returns:
        function: 转录函数，签名为 transcribe(audio_path: str) -> str
    """
    from app.modules import whisper_ai
    logger.info("使用 Whisper ASR")
    return whisper_ai.transcribe_audio


# 预加载转录函数
_transcribe = None


def transcribe_audio(audio_path: str) -> str:
    """
    统一的语音识别入口函数

    Args:
        audio_path: 音频文件路径

    Returns:
        识别出的文本
    """
    global _transcribe
    if _transcribe is None:
        _transcribe = get_transcribe_function()
    return _transcribe(audio_path)
