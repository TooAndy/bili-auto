import requests
import json
from pathlib import Path
from app.utils.logger import get_logger
from config import Config

logger = get_logger("dynamic")


class DynamicFetcher:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        if Config.BILIBILI_COOKIE:
            self.headers["Cookie"] = Config.BILIBILI_COOKIE

        self.image_dir = Path("data/dynamic_images")
        self.image_dir.mkdir(parents=True, exist_ok=True)

    def fetch_dynamic(self, mid: str, offset: int = 0) -> list:
        url = "https://api.bilibili.com/x/polymer/v1/feed/space"
        params = {
            "host_mid": mid,
            "offset": offset,
            "features": "forward"
        }

        resp = requests.get(url, params=params, headers=self.headers, timeout=20)
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
        dynamic_id = item.get("id_str")
        dynamic_type = item.get("type")

        if dynamic_type not in [256, 2, 1, 4]:
            return None

        modules = item.get("modules", {})
        module_content = modules.get("module_content", {})
        text = module_content.get("content", "").strip()

        image_urls = []
        for img in module_content.get("image_urls", []):
            if isinstance(img, dict) and img.get("src"):
                image_urls.append(img.get("src"))

        pub_time = modules.get("module_author", {}).get("pub_time", "")

        return {
            "dynamic_id": dynamic_id,
            "type": dynamic_type,
            "text": text,
            "image_urls": image_urls,
            "pub_time": pub_time,
            "images": []
        }

    def download_images(self, dynamic: dict) -> dict:
        images = []
        for idx, url in enumerate(dynamic.get("image_urls", [])):
            try:
                resp = requests.get(url, timeout=20)
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
