import requests
from typing import List, Optional
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


def fetch_all_videos(mid: str, start_date: Optional[int] = None, end_date: Optional[int] = None) -> List[dict]:
    """
    获取 UP 主所有视频（支持分页和日期范围过滤）

    Args:
        mid: UP 主 ID
        start_date: 开始日期时间戳（Unix timestamp），None 表示不限制
        end_date: 结束日期时间戳（Unix timestamp），None 表示不限制

    Returns:
        视频列表，按发布时间倒序
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    }
    if Config.BILIBILI_COOKIE:
        headers["Cookie"] = Config.BILIBILI_COOKIE

    all_videos = []
    page = 1
    page_size = 30  # B站 API 每页最多30条

    logger.info("开始获取 UP 主 %s 的所有视频...", mid)

    while True:
        url = "https://api.bilibili.com/x/space/arc/search"
        params = {
            "mid": mid,
            "ps": page_size,
            "pn": page
        }

        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            logger.error("bilibili API error (page %d): %s", page, data.get("message"))
            break

        items = data.get("data", {}).get("list", {}).get("vlist", [])

        if not items:
            # 没有更多数据
            break

        page_videos = []
        for item in items:
            pubdate = item.get("created", 0)

            # 日期范围过滤
            if start_date and pubdate < start_date:
                # 视频发布时间早于开始日期，由于是倒序，后面的视频更早，可以停止
                logger.debug("视频 %s 发布于 %d，早于开始日期 %d，停止获取",
                            item.get("bvid"), pubdate, start_date)
                return all_videos

            if end_date and pubdate > end_date:
                # 视频发布时间晚于结束日期，跳过
                logger.debug("跳过视频 %s，发布于 %d，晚于结束日期 %d",
                            item.get("bvid"), pubdate, end_date)
                continue

            page_videos.append({
                "bvid": item.get("bvid"),
                "title": item.get("title"),
                "pubdate": pubdate,
                "duration": item.get("length"),
                "pic": item.get("pic"),
                "description": item.get("description", ""),
                "comment": item.get("comment", 0),
                "play": item.get("play", 0),
            })

        all_videos.extend(page_videos)
        logger.info("第 %d 页获取到 %d 个视频，累计 %d 个", page, len(page_videos), len(all_videos))

        # 检查是否还有更多页
        page_info = data.get("data", {}).get("page", {})
        total = page_info.get("count", 0)
        if len(all_videos) >= total:
            logger.info("已获取所有视频，共 %d 个", len(all_videos))
            break

        page += 1

    return all_videos


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
