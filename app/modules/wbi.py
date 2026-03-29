"""
B站 WBI 签名实现

WBI (Web Browser Interface) 是 B站的反爬虫机制
"""
import hashlib
import time
import random
import string
from typing import Dict
from app.utils.logger import get_logger
from config import Config

logger = get_logger("wbi")


class WBISigner:
    """WBI 签名器"""

    def __init__(self):
        self._img_key = None
        self._sub_key = None
        self._mixed_key = None
        self._last_refresh = 0
        self._refresh_interval = 3600  # 密钥有效期1小时

    def _get_keys(self) -> tuple:
        """
        从 B站获取 img_key 和 sub_key

        Returns:
            (img_key, sub_key)
        """
        import requests

        url = "https://api.bilibili.com/x/web-interface/nav"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.bilibili.com",
        }
        if Config.BILIBILI_COOKIE:
            headers["Cookie"] = Config.BILIBILI_COOKIE

        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 0:
                logger.error("获取 WBI 密钥失败: %s", data.get("message"))
                return None, None

            wbi_img = data.get("data", {}).get("wbi_img", {})
            img_url = wbi_img.get("img_url", "")
            sub_url = wbi_img.get("sub_url", "")

            # 从 URL 中提取密钥
            # 格式: https://xxx.xxxx.com/xxxxkey.jpg
            img_key = img_url.split("/")[-1].split(".")[0]
            sub_key = sub_url.split("/")[-1].split(".")[0]

            logger.debug("获取 WBI 密钥成功: img_key=%s, sub_key=%s", img_key[:8] + "...", sub_key[:8] + "...")
            return img_key, sub_key

        except Exception as e:
            logger.error("获取 WBI 密钥异常: %s", e)
            return None, None

    def _mix_keys(self, img_key: str, sub_key: str) -> str:
        """
        混合密钥

        根据特定的规则混合 img_key 和 sub_key
        规则：从 img_key 和 sub_key 中按特定位置取字符

        Args:
            img_key: 图片密钥
            sub_key: 子密钥

        Returns:
            混合后的密钥
        """
        # B站的混合规则（前32位）
        # 偶数位从 img_key 取，奇数位从 sub_key 取
        mixed = []
        for i in range(32):
            if i % 2 == 0:
                mixed.append(img_key[i])
            else:
                mixed.append(sub_key[i])
        return "".join(mixed)

    def _get_mixed_key(self) -> str:
        """
        获取混合密钥，如果过期则刷新

        Returns:
            混合后的密钥
        """
        current_time = int(time.time())

        # 检查是否需要刷新
        if (self._mixed_key is None or
            current_time - self._last_refresh > self._refresh_interval):

            img_key, sub_key = self._get_keys()
            if img_key and sub_key:
                self._img_key = img_key
                self._sub_key = sub_key
                self._mixed_key = self._mix_keys(img_key, sub_key)
                self._last_refresh = current_time
            else:
                logger.warning("获取 WBI 密钥失败，使用缓存密钥")

        return self._mixed_key

    def sign(self, params: Dict) -> Dict:
        """
        对参数进行 WBI 签名

        Args:
            params: 原始参数

        Returns:
            添加了 w_rid 和 wts 的参数
        """
        # 添加时间戳
        params = params.copy()
        params["wts"] = int(time.time())

        # 生成随机设备指纹参数（简化版）
        # 这些参数是 B站用于反爬虫的，可以简化或随机生成
        params["platform"] = "web"
        params["web_location"] = "333.1387"

        # 按字母顺序排序参数
        sorted_params = sorted(params.items())
        query_string = "&".join([f"{k}={v}" for k, v in sorted_params])

        # 获取混合密钥
        mixed_key = self._get_mixed_key()

        # 生成签名: md5(query_string + mixed_key)
        sign_string = query_string + mixed_key
        w_rid = hashlib.md5(sign_string.encode()).hexdigest()

        params["w_rid"] = w_rid
        return params


# 全局签名器实例
_signer = WBISigner()


def sign_params(params: Dict) -> Dict:
    """
    对参数进行 WBI 签名（便捷函数）

    Args:
        params: 原始参数

    Returns:
        添加了 w_rid 和 wts 的参数
    """
    return _signer.sign(params)
