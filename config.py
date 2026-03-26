import os
from pathlib import Path

from dotenv import load_dotenv

# 载入项目根目录 .env
env_path = Path(__file__).resolve().parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()


class Config:
    # B站
    BILIBILI_COOKIE = os.getenv("BILIBILI_COOKIE", "")

    # LLM
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

    # 推送
    FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK", "")
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

    WECHAT_CORP_ID = os.getenv("WECHAT_CORP_ID", "")
    WECHAT_CORP_SECRET = os.getenv("WECHAT_CORP_SECRET", "")
    WECHAT_AGENT_ID = os.getenv("WECHAT_AGENT_ID", "")
    WECHAT_TO_USER = os.getenv("WECHAT_TO_USER", "@all")

    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/bili.db")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
