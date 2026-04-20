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

    # B站 Cookie 自动刷新
    # refresh_token 用于自动刷新 Cookie，从浏览器获取：
    # 1. 登录B站后在 Console 运行: localStorage.getItem('ac_time_value')
    # 2. 或从登录响应中获取
    refresh_token = os.getenv("refresh_token", "")

    # LLM
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "")

    # 推送
    FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK", "")
    FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
    FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
    FEISHU_RECEIVE_ID = os.getenv("FEISHU_RECEIVE_ID", "")
    FEISHU_RECEIVE_ID_TYPE = os.getenv("FEISHU_RECEIVE_ID_TYPE", "open_id")
    # 飞书文档（用于保存 summary.md
    FEISHU_DOCS_ENABLED = os.getenv("FEISHU_DOCS_ENABLED", "false").lower() == "true"
    FEISHU_DOCS_FOLDER_TOKEN = os.getenv("FEISHU_DOCS_FOLDER_TOKEN", "")  # 顶级文件夹 token
    FEISHU_DOCS_SPACE_ID = os.getenv("FEISHU_DOCS_SPACE_ID", "")
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

    # 微信企业号
    WECHAT_CORP_ID = os.getenv("WECHAT_CORP_ID", "")
    WECHAT_CORP_SECRET = os.getenv("WECHAT_CORP_SECRET", "")
    WECHAT_AGENT_ID = os.getenv("WECHAT_AGENT_ID", "")
    WECHAT_TO_USER = os.getenv("WECHAT_TO_USER", "@all")
    WECHAT_WEBHOOK_KEY = os.getenv("WECHAT_WEBHOOK_KEY", "")

    # 推送渠道配置
    # 逗号分隔的渠道列表，如 "feishu,telegram,wechat"
    # 设为空则不推送，留空则使用代码中的默认值（飞书）
    PUSH_CHANNELS = os.getenv("PUSH_CHANNELS", "")

    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/bili.db")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # 调度间隔（分钟）
    VIDEO_CHECK_INTERVAL = int(os.getenv("VIDEO_CHECK_INTERVAL", "10"))
    DYNAMIC_CHECK_INTERVAL = int(os.getenv("DYNAMIC_CHECK_INTERVAL", "5"))

    # ASR 语音识别配置
    # Whisper 模型: tiny|base|small|medium|large
    WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
    WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")  # cpu|cuda

    # Whisper.cpp 配置（可选）
    USE_WHISPER_CPP = os.getenv("USE_WHISPER_CPP", "false").lower() == "true"
    WHISPER_CPP_CLI = os.getenv("WHISPER_CPP_CLI", "")
    WHISPER_CPP_MODEL = os.getenv("WHISPER_CPP_MODEL", "")
