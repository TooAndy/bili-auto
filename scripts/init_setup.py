#!/usr/bin/env python3
"""初始化项目：创建目录、数据库、下载模型"""
from pathlib import Path
from app.models.database import init_services
from app.utils.logger import get_logger

logger = get_logger("init_setup")


def setup():
    print("开始初始化 bili 项目")
    for p in ["data/subtitles", "data/audio", "data/dynamic_images", "logs"]:
        Path(p).mkdir(parents=True, exist_ok=True)
        print(f"目录已创建: {p}")

    init_services()
    print("服务初始化完成")

    # 快速验证模型
    try:
        from app.modules.whisper_ai import model
        print("Whisper 模型已加载")
    except Exception as e:
        print("Whisper 模型加载失败，首次运行时会自动下载：", e)

    print("初始化完成。请配置 .env 并运行 python main.py")


if __name__ == "__main__":
    setup()
