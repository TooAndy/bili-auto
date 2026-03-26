import json
import os
from app.utils.logger import get_logger
from config import Config

logger = get_logger("llm")

try:
    import openai
    openai.api_key = Config.OPENAI_API_KEY
except ImportError:
    openai = None


def summarize(text: str, title: str = "", duration: int = 0) -> dict:
    text = (text or "").strip()
    if not text:
        return {
            "title": title,
            "summary": "",
            "key_points": [],
            "timeline": [],
            "tags": [],
            "insights": "",
            "duration_minutes": duration,
            "url": ""
        }

    if Config.OPENAI_API_KEY and openai:
        system = "你是高质量内容分析助手。"
        user = f"标题: {title}\n时长: {duration} 分钟\n\n{text[:6500]}"

        try:
            resp = openai.ChatCompletion.create(
                model=Config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ],
                temperature=0.2,
                max_tokens=500
            )
            reply = resp.choices[0].message.content.strip()

            return {
                "title": title,
                "summary": reply[:500],
                "key_points": [],
                "timeline": [],
                "tags": [],
                "insights": "",
                "duration_minutes": duration,
                "url": ""
            }
        except Exception as e:
            logger.warning("OpenAI 调用失败，降级简易摘要: %s", e)

    # 本地简易摘要回退
    sentences = text.replace("。", "。\n").splitlines()
    summary = "。".join(sentences[:4])
    key_points = [s.strip() for s in sentences[:3] if s.strip()]

    return {
        "title": title,
        "summary": summary[:300],
        "key_points": key_points,
        "timeline": [],
        "tags": [],
        "insights": "",
        "duration_minutes": duration,
        "url": ""
    }
