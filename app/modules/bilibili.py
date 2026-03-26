import requests
from typing import List
from config import Config
from app.utils.logger import get_logger

logger = get_logger("bilibili")


def fetch_channel_videos(mid: str, limit: int = 5) -> List[dict]:
    """获取 UP 主最新视频列表"""
    url = "https://api.bilibili.com/x/space/arc/search"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    }
    if Config.BILIBILI_COOKIE:
        headers["Cookie"] = Config.BILIBILI_COOKIE

    resp = requests.get(url, params={"mid": mid, "ps": limit, "pn": 1}, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if data.get("code") != 0:
        logger.error("bilibili channel videos fetch error: %s", data.get("message"))
        return []

    items = data.get("data", {}).get("list", {}).get("vlist", [])
    videos = []

    for item in items:
        videos.append({
            "bvid": item.get("bvid"),
            "title": item.get("title"),
            "pubdate": item.get("created", 0),
            "duration": item.get("length"),
            "pic": item.get("pic"),
        })

    return videos


def get_subtitle_info(bvid: str, cid: str = None) -> dict:
    """查询视频是否有字幕（备用）"""
    url = "https://api.bilibili.com/x/player/v2"
    headers = {
        "User-Agent": "Mozilla/5.0",
    }
    if Config.BILIBILI_COOKIE:
        headers["Cookie"] = Config.BILIBILI_COOKIE

    params = {"bvid": bvid}
    if cid:
        params["cid"] = cid

    resp = requests.get(url, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()
