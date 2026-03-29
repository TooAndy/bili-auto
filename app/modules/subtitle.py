import requests
from app.utils.logger import get_logger
from app.modules.bilibili import get_subtitle_info
from config import Config

logger = get_logger("subtitle")


def _get_session() -> requests.Session:
    """创建并配置一个 Session 实例"""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.bilibili.com",
    })
    if Config.BILIBILI_COOKIE:
        session.headers.update({"Cookie": Config.BILIBILI_COOKIE})
    return session


def get_subtitles(bvid: str) -> str:
    """从B站视频尝试读取字幕, 失败返回空字符串"""
    session = _get_session()
    try:
        info = get_subtitle_info(bvid)
        subtitle_list = info.get("data", {}).get("subtitle", {}).get("list", [])

        if not subtitle_list:
            return ""

        captions = []
        for item in subtitle_list:
            sub_url = item.get("subtitle_url") or item.get("lan_url")
            if not sub_url:
                continue

            r = session.get(sub_url, timeout=20)
            r.raise_for_status()

            body = r.json().get("body") or []
            for line in body:
                text = line.get("content") if isinstance(line, dict) else ""
                if text:
                    captions.append(text.strip())

        return "\n".join(captions)

    except Exception as e:
        logger.warning("未能获取B站字幕 %s: %s", bvid, e)
        return ""
    finally:
        session.close()
