import requests
import time
from typing import List, Optional
from config import Config
from app.utils.logger import get_logger
from app.modules.wbi import sign_params

logger = get_logger("bilibili")


def _check_cookie() -> None:
    """检查是否配置了 BILIBILI_COOKIE"""
    if not Config.BILIBILI_COOKIE:
        raise RuntimeError(
            "批量获取视频需要配置 BILIBILI_COOKIE 以避免限流。\n"
            "请在 .env 文件中设置 BILIBILI_COOKIE。\n"
            "获取方式：登录 B站 后，在浏览器开发者工具中复制 Cookie 值"
        )


def _get_session() -> requests.Session:
    """
    创建并配置一个 Session 实例

    使用 Session 可以复用 TCP 连接，减少 API 请求限流风险
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.bilibili.com",
        "Origin": "https://www.bilibili.com",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
    })
    if Config.BILIBILI_COOKIE:
        session.headers.update({"Cookie": Config.BILIBILI_COOKIE})
    return session


def fetch_channel_videos(mid: str, limit: int = 5) -> List[dict]:
    """获取 UP 主最新视频列表"""
    session = _get_session()
    url = "https://api.bilibili.com/x/space/arc/search"

    try:
        resp = session.get(url, params={"mid": mid, "ps": limit, "pn": 1}, timeout=15)
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
    finally:
        session.close()


def fetch_all_videos(mid: str, start_date: Optional[int] = None, end_date: Optional[int] = None) -> List[dict]:
    """
    获取 UP 主所有视频（支持分页和日期范围过滤）

    使用 WBI 签名接口，减少限流风险

    Args:
        mid: UP 主 ID
        start_date: 开始日期时间戳（Unix timestamp），None 表示不限制
        end_date: 结束日期时间戳（Unix timestamp），None 表示不限制

    Returns:
        视频列表，按发布时间倒序
    """
    # 检查 Cookie 配置
    _check_cookie()

    session = _get_session()
    url = "https://api.bilibili.com/x/space/wbi/arc/search"

    all_videos = []
    page = 1
    page_size = 25  # WBI 接口建议使用 25

    logger.info("开始获取 UP 主 %s 的所有视频 (使用 WBI 签名)...", mid)

    try:
        while True:
            # 构建参数（参考 curl 命令）
            params = {
                "mid": str(mid),
                "ps": str(page_size),
                "pn": str(page),
                "tid": "0",
                "special_type": "",
                "order": "pubdate",
                "index": "0",
                "keyword": "",
                "order_avoided": "true",
            }

            # WBI 签名
            signed_params = sign_params(params)
            logger.debug("WBI 签名参数: %s", {k: v for k, v in signed_params.items() if k not in ['w_rid', 'wts']})

            resp = session.get(url, params=signed_params, timeout=15)
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

            # 每页之间延迟，避免限流
            if page > 1:
                time.sleep(0.5)

        return all_videos
    finally:
        session.close()


def get_subtitle_info(bvid: str, cid: str = None) -> dict:
    """查询视频是否有字幕（备用）"""
    session = _get_session()
    url = "https://api.bilibili.com/x/player/v2"

    try:
        params = {"bvid": bvid}
        if cid:
            params["cid"] = cid

        resp = session.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    finally:
        session.close()
