from faster_whisper import WhisperModel
from app.utils.logger import get_logger

logger = get_logger("whisper")

model = WhisperModel(
    "small",
    device="cpu",
    compute_type="int8",
    download_root="models"
)


def transcribe_audio(audio_path: str) -> str:
    logger.info("Whisper 识别: %s", audio_path)
    segments, _ = model.transcribe(
        audio_path,
        language="zh",
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=True
    )
    text = "\n".join([segment.text for segment in segments])
    logger.info("Whisper 完成，文本长度 %d", len(text))
    return text
