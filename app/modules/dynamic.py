import requests
import json
from datetime import datetime
from pathlib import Path
from app.utils.logger import get_logger
from config import Config
from app.modules.wbi import WBISigner

logger = get_logger("dynamic")


class DynamicFetcher:
    def __init__(self):
        # 使用 Session 复用连接
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0",
            "Referer": "https://space.bilibili.com",
            "Origin": "https://space.bilibili.com",
        })
        if Config.BILIBILI_COOKIE:
            self.session.headers.update({"Cookie": Config.BILIBILI_COOKIE})

        self.image_dir = Path("data/dynamic_images")
        self.image_dir.mkdir(parents=True, exist_ok=True)

        # WBI 签名器
        self.wbi_signer = WBISigner()

    def close(self):
        """关闭 Session"""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def fetch_dynamic(self, mid: str, offset: str = "") -> list:
        """
        获取 UP主动态

        Args:
            mid: UP主 ID
            offset: 分页偏移量（字符串格式）

        Returns:
            动态列表
        """
        url = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space"

        # 基础参数
        params = {
            "host_mid": mid,
            "offset": offset,
            "timezone_offset": "-480",
            "platform": "web",
            "features": "itemOpusStyle,listOnlyfans,opusBigCover,onlyfansVote,forwardListHidden,decorationCard,commentsNewVersion,onlyfansAssetsV2,ugcDelete,onlyfansQaCard,avatarAutoTheme,sunflowerStyle,cardsEnhance,eva3CardOpus,eva3CardVideo,eva3CardComment,eva3CardUser",
            "web_location": "333.1387",
        }

        # WBI 签名
        params = self.wbi_signer.sign(params)

        resp = self.session.get(url, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            logger.error("动态拉取失败：%s", data.get("message"))
            return []

        items = data.get("data", {}).get("items", [])
        dynamics = []

        for item in items:
            parsed = self._parse_dynamic(item)
            if parsed:
                dynamics.append(parsed)

        return dynamics

    def _parse_dynamic(self, item: dict) -> dict:
        """
        解析动态数据

        新 API 返回的动态类型：
        - DYNAMIC_TYPE_AV: 视频动态
        - DYNAMIC_TYPE_WORD: 纯文字动态
        - DYNAMIC_TYPE_DRAW: 图片动态
        - DYNAMIC_TYPE_OPUS: 图文动态（大图）
        """
        dynamic_id = item.get("id_str")
        dynamic_type_str = item.get("type", "")

        # 跳过转发动态
        if item.get("orig"):
            return None

        modules = item.get("modules", {})
        module_author = modules.get("module_author", {})
        module_dynamic = modules.get("module_dynamic", {})

        # 获取文本内容
        text = ""
        image_urls = []

        # 根据动态类型解析
        if dynamic_type_str == "DYNAMIC_TYPE_AV":
            # 视频动态
            major = module_dynamic.get("major") or {}
            archive = major.get("archive") or {}
            text = archive.get("title", "")
            desc = archive.get("desc", "")
            if desc:
                text = f"{text}\n{desc}" if text else desc

        elif dynamic_type_str in ["DYNAMIC_TYPE_WORD", "DYNAMIC_TYPE_DRAW", "DYNAMIC_TYPE_OPUS"]:
            # 文字/图片动态
            major = module_dynamic.get("major") or {}
            if dynamic_type_str == "DYNAMIC_TYPE_OPUS":
                # 图文动态（大图）
                opus = major.get("opus") or {}
                text = opus.get("summary", "") or opus.get("title", "")
                # 获取图片
                for img in opus.get("images") or []:
                    if isinstance(img, dict):
                        image_urls.append(img.get("url", ""))
            else:
                # 普通文字/图片动态
                common = major.get("common") or {}
                text = common.get("desc", "")
                # 获取图片
                for img in common.get("images") or []:
                    if isinstance(img, dict):
                        src = img.get("src", "")
                        if src:
                            image_urls.append(src)

        else:
            # 其他类型不处理
            return None

        text = text.strip()
        if not text:
            return None

        # 获取发布时间
        pub_ts = module_author.get("pub_ts", 0)
        pub_time = module_author.get("pub_time", "")

        # 将时间戳转换为 datetime 对象
        pub_datetime = None
        if pub_ts and isinstance(pub_ts, int) and pub_ts > 0:
            pub_datetime = datetime.fromtimestamp(pub_ts)

        return {
            "dynamic_id": dynamic_id,
            "type": dynamic_type_str,
            "text": text,
            "image_urls": image_urls,
            "pub_time": pub_datetime,
            "pub_ts": pub_ts,
            "images": []
        }

    def download_images(self, dynamic: dict) -> dict:
        images = []
        for idx, url in enumerate(dynamic.get("image_urls", [])):
            try:
                resp = self.session.get(url, timeout=20)
                resp.raise_for_status()
                filename = f"{dynamic['dynamic_id']}_{idx}.jpg"
                path = self.image_dir / filename
                path.write_bytes(resp.content)
                images.append(str(path))
            except Exception as e:
                logger.warning("下载动态图片失败: %s, %s", url, e)

        dynamic["images"] = images
        return dynamic


def should_push_dynamic(dynamic: dict) -> bool:
    text = (dynamic.get("text", "") or "").strip()

    if not text:
        return False

    if text.startswith("转发") or text.startswith("//@"):
        return False

    if text.startswith("http") and len(text) < 120:
        return False

    if len(text) < 10:
        return False

    banned_keywords = ["秒杀", "折扣", "限时"]
    if any(kw in text for kw in banned_keywords):
        return False

    return True
