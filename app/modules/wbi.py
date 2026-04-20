"""
B站 WBI 签名实现

WBI (Web Browser Interface) 是 B站的反爬虫机制
参考：https://github.com/SocialSisterYi/bilibili-API-collect
"""
import hashlib
import time
import urllib.parse
from functools import reduce
from typing import Dict, Tuple
import requests
from app.utils.logger import get_logger
from config import Config

logger = get_logger("wbi")

# WBI 混合密钥打乱表
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52
]


class WBISigner:
    """WBI 签名器"""

    def __init__(self):
        self._img_key = None
        self._sub_key = None
        self._mixin_key = None
        self._last_refresh = 0
        self._refresh_interval = 3600  # 密钥有效期1小时

    def _get_keys(self) -> Tuple[str, str]:
        """
        从 B站获取 img_key 和 sub_key

        Returns:
            (img_key, sub_key)
        """
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
            img_key = img_url.rsplit('/', 1)[1].split('.')[0]
            sub_key = sub_url.rsplit('/', 1)[1].split('.')[0]

            logger.debug("获取 WBI 密钥成功")
            return img_key, sub_key

        except Exception as e:
            logger.error("获取 WBI 密钥异常: %s", e)
            return None, None

    def _get_mixin_key(self, img_key: str, sub_key: str) -> str:
        """
        对 imgKey 和 subKey 进行字符顺序打乱编码

        Args:
            img_key: 图片密钥
            sub_key: 子密钥

        Returns:
            混合后的密钥（32位）
        """
        # 将 img_key 和 sub_key 拼接后，按照打乱表重新排列
        orig = img_key + sub_key
        return reduce(lambda s, i: s + orig[i], MIXIN_KEY_ENC_TAB, '')[:32]

    def _refresh_mixin_key(self) -> str:
        """
        刷新混合密钥，如果过期则重新获取

        Returns:
            混合后的密钥
        """
        current_time = int(time.time())

        # 检查是否需要刷新
        if (self._mixin_key is None or
            current_time - self._last_refresh > self._refresh_interval):

            img_key, sub_key = self._get_keys()
            if img_key and sub_key:
                self._img_key = img_key
                self._sub_key = sub_key
                self._mixin_key = self._get_mixin_key(img_key, sub_key)
                self._last_refresh = current_time
            else:
                logger.error("无法获取 WBI 密钥，Cookie 可能已过期或无效")
                raise ValueError("WBI 密钥获取失败，无法进行签名")

        return self._mixin_key

    def sign(self, params: Dict) -> Dict:
        """
        对参数进行 WBI 签名

        Args:
            params: 原始参数

        Returns:
            添加了 w_rid 和 wts 的参数
        """
        # 复制参数，避免修改原始数据
        params = params.copy()

        # 添加时间戳
        params['wts'] = round(time.time())

        # 按照 key 的字母顺序排序
        params = dict(sorted(params.items()))

        # 过滤 value 中的 "!'()*" 字符
        params = {
            k: ''.join(filter(lambda chr: chr not in "!'()*", str(v)))
            for k, v in params.items()
        }

        # 序列化参数
        query = urllib.parse.urlencode(params)

        # 获取混合密钥
        mixin_key = self._refresh_mixin_key()

        # 计算 w_rid: md5(query + mixin_key)
        wbi_sign = hashlib.md5((query + mixin_key).encode()).hexdigest()

        params['w_rid'] = wbi_sign
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
