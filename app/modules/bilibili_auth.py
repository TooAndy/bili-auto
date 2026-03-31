# -*- coding: utf-8 -*-
"""
B站认证和Cookie管理模块

实现B站Cookie自动刷新机制
参考文档: https://socialsisteryi.github.io/bilibili-API-collect/docs/login/cookie_refresh.html
参考文章: https://blog.csdn.net/gitblog_00169/article/details/152153957
"""

import asyncio
import json
import logging
import os
import time
import binascii
from pathlib import Path
from typing import Optional, Tuple

import aiohttp

from app.utils.logger import get_logger

# 尝试导入加密库
try:
    from Crypto.Cipher import PKCS1_OAEP
    from Crypto.PublicKey import RSA
    from Crypto.Hash import SHA256
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

logger = get_logger("bilibili_auth")


class BilibiliAuth:
    """B站认证管理类"""

    # API端点
    CHECK_COOKIE_URL = "https://passport.bilibili.com/x/passport-login/web/cookie/info"
    GET_REFRESH_CSRF_URL = "https://www.bilibili.com/correspond/1/{correspond_path}"
    REFRESH_COOKIE_URL = (
        "https://passport.bilibili.com/x/passport-login/web/cookie/refresh"
    )
    CONFIRM_REFRESH_URL = (
        "https://passport.bilibili.com/x/passport-login/web/confirm/refresh"
    )
    # SSO 跨域登录端点（常用子域名）
    SSO_URLS = [
        "https://passport.bilibili.com/x/passport-login/sso/cookie",
        "https://www.bilibili.com/x/passport-login/sso/cookie",
        "https://space.bilibili.com/x/passport-login/sso/cookie",
        "https://message.bilibili.com/x/passport-login/sso/cookie",
    ]

    # B站 RSA 公钥（用于生成 CorrespondPath）
    BILIBILI_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDLgd2OAkcGVtoE3ThUREbio0Eg
Uc/prcajMKXvkCKFCWhJYJcLkcM2DKKcSeFpD/j6Boy538YXnR6VhcuUJOhH2x71
nzPjfdTcqMz7djHum0qSZA0AyCBDABUqCrfNgCiJ00Ra7GmRj+YCK1NJEuewlb40
JNrRuoEUXpabUzGB8QIDAQAB
-----END PUBLIC KEY-----"""

    # 存储路径
    AUTH_DATA_PATH = Path("data/bilibili_auth.json")

    def __init__(self, env_path: Optional[Path] = None):
        """
        初始化认证管理器

        Args:
            env_path: .env 文件路径，默认为项目根目录的 .env
        """
        self.auth_data = self._load_auth_data()

        # 设置 .env 文件路径
        if env_path is None:
            self.env_path = Path(__file__).resolve().parent.parent.parent / ".env"
        else:
            self.env_path = Path(env_path)

    def _load_auth_data(self) -> dict:
        """加载认证数据"""
        if self.AUTH_DATA_PATH.exists():
            try:
                with open(self.AUTH_DATA_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载认证数据失败: {e}")
        return {}

    def _save_auth_data(self) -> None:
        """保存认证数据"""
        try:
            os.makedirs(self.AUTH_DATA_PATH.parent, exist_ok=True)
            with open(self.AUTH_DATA_PATH, "w", encoding="utf-8") as f:
                json.dump(self.auth_data, f, ensure_ascii=False, indent=2)
            logger.debug("认证数据已保存到 %s", self.AUTH_DATA_PATH)
        except Exception as e:
            logger.error(f"保存认证数据失败: {e}")

    def _update_env_file(self, updates: dict) -> bool:
        """
        更新 .env 文件中的配置

        Args:
            updates: 要更新的键值对字典

        Returns:
            是否成功
        """
        try:
            env_file = self.env_path

            # 读取现有配置
            env_lines = []
            if env_file.exists():
                with open(env_file, "r", encoding="utf-8") as f:
                    env_lines = f.readlines()

            # 更新或添加配置
            for key, value in updates.items():
                found = False
                for i, line in enumerate(env_lines):
                    if line.startswith(f"{key}="):
                        env_lines[i] = f"{key}={value}\n"
                        found = True
                        break

                if not found:
                    env_lines.append(f"{key}={value}\n")

            # 写回文件
            with open(env_file, "w", encoding="utf-8") as f:
                f.writelines(env_lines)

            logger.info("已更新 .env 文件: %s", ", ".join(updates.keys()))
            return True

        except Exception as e:
            logger.error(f"更新 .env 文件失败: {e}", exc_info=True)
            return False

    def set_refresh_token(self, refresh_token: str, save_to_env: bool = True) -> None:
        """
        设置refresh_token

        Args:
            refresh_token: 从登录接口获得的refresh_token
            save_to_env: 是否同时保存到 .env 文件
        """
        self.auth_data["refresh_token"] = refresh_token
        self.auth_data["last_refresh_time"] = time.time()
        self._save_auth_data()

        if save_to_env:
            self._update_env_file({"refresh_token": refresh_token})

        logger.info("refresh_token已更新")

    def get_refresh_token(self) -> Optional[str]:
        """
        获取refresh_token
        优先从.env读取，如果没有则从auth_data读取
        """
        # 优先从环境变量读取（.env文件）
        env_refresh_token = os.getenv("refresh_token")
        if env_refresh_token:
            return env_refresh_token

        # 如果env中没有，从json文件读取（兼容旧版本）
        return self.auth_data.get("refresh_token")

    def parse_cookie_to_dict(self, cookie_str: str) -> dict:
        """
        将Cookie字符串解析为字典

        Args:
            cookie_str: Cookie字符串

        Returns:
            Cookie字典
        """
        cookie_dict = {}
        for item in cookie_str.split(";"):
            item = item.strip()
            if "=" in item:
                key, value = item.split("=", 1)
                cookie_dict[key] = value
        return cookie_dict

    def build_cookie_from_dict(self, cookie_dict: dict) -> str:
        """
        从字典构建Cookie字符串

        Args:
            cookie_dict: Cookie字典

        Returns:
            Cookie字符串
        """
        return "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])

    async def check_need_refresh(self, cookie: str) -> Tuple[bool, Optional[int]]:
        """
        检查Cookie是否需要刷新

        Args:
            cookie: 当前Cookie字符串

        Returns:
            (是否需要刷新, 时间戳)
        """
        try:
            from config import Config

            # 提取bili_jct作为csrf
            csrf = self._extract_bili_jct(cookie)

            params = {}
            if csrf:
                params["csrf"] = csrf

            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
                "Cookie": cookie,
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.CHECK_COOKIE_URL, params=params, headers=headers, timeout=10
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("code") == 0:
                            result = data.get("data", {})
                            need_refresh = result.get("refresh", False)
                            timestamp = result.get("timestamp")

                            logger.info(
                                f"Cookie检查完成: need_refresh={need_refresh}, timestamp={timestamp}"
                            )
                            return need_refresh, timestamp
                        else:
                            logger.error(f"检查Cookie失败: {data.get('message')}")
                    else:
                        logger.error(f"检查Cookie失败，HTTP状态码: {resp.status}")

        except Exception as e:
            logger.error(f"检查Cookie时出错: {e}")

        return False, None

    async def get_refresh_csrf(
        self, correspond_path: str, cookie: str
    ) -> Optional[str]:
        """
        获取 refresh_csrf

        Args:
            correspond_path: 生成的 CorrespondPath
            cookie: 当前 Cookie

        Returns:
            refresh_csrf 字符串或 None
        """
        try:
            url = self.GET_REFRESH_CSRF_URL.format(correspond_path=correspond_path)

            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
                "Cookie": cookie,
                "Referer": "https://www.bilibili.com/",
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as resp:
                    if resp.status == 200:
                        # 返回的是 HTML，需要从 <div id="1-name"> 中提取
                        text = await resp.text()

                        # 简单的字符串提取，找 <div id="1-name">...</div>
                        marker_start = '<div id="1-name">'
                        marker_end = "</div>"

                        start_idx = text.find(marker_start)
                        if start_idx != -1:
                            start_idx += len(marker_start)
                            end_idx = text.find(marker_end, start_idx)
                            if end_idx != -1:
                                refresh_csrf = text[start_idx:end_idx].strip()
                                if refresh_csrf:
                                    logger.info("获取 refresh_csrf 成功")
                                    logger.debug(f"refresh_csrf: {refresh_csrf[:30]}...")
                                    return refresh_csrf

                        logger.warning(f"未能从 HTML 中提取 refresh_csrf")
                        logger.debug(f"响应内容: {text[:300]}")
                    else:
                        logger.error(f"获取 refresh_csrf 失败，HTTP状态码: {resp.status}")

        except Exception as e:
            logger.error(f"获取 refresh_csrf 时出错: {e}", exc_info=True)

        return None

    async def sso_cross_domain_login(self, cookie: str) -> bool:
        """
        SSO 跨域登录，同步 Cookie 到各个子域名

        Args:
            cookie: 新 Cookie

        Returns:
            是否成功（至少一个成功即可）
        """
        success_count = 0

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
            "Cookie": cookie,
        }

        async with aiohttp.ClientSession() as session:
            for sso_url in self.SSO_URLS:
                try:
                    async with session.get(sso_url, headers=headers, timeout=10) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("code") == 0:
                                success_count += 1
                                logger.debug(f"SSO 登录成功: {sso_url}")
                            else:
                                logger.debug(f"SSO 登录返回非0: {sso_url}, code={data.get('code')}")
                        else:
                            logger.debug(f"SSO 登录 HTTP {resp.status}: {sso_url}")
                except Exception as e:
                    logger.debug(f"SSO 登录出错: {sso_url}, {e}")

        logger.info(f"SSO 跨域登录完成: {success_count}/{len(self.SSO_URLS)} 成功")
        return success_count > 0

    async def refresh_cookie(
        self, old_cookie: str, refresh_csrf: str
    ) -> Optional[Tuple[str, str]]:
        """
        刷新Cookie

        Args:
            old_cookie: 旧Cookie
            refresh_csrf: 获取到的 refresh_csrf

        Returns:
            (新Cookie, 新refresh_token) 或 None
        """
        try:
            refresh_token = self.get_refresh_token()
            if not refresh_token:
                logger.warning("没有refresh_token，无法刷新Cookie")
                return None

            # 提取csrf
            csrf = self._extract_bili_jct(old_cookie)
            if not csrf:
                logger.error("无法从Cookie中提取bili_jct")
                return None

            # 构造请求
            data = {
                "csrf": csrf,
                "refresh_csrf": refresh_csrf,
                "refresh_token": refresh_token,
                "source": "main_web",
            }

            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
                "Cookie": old_cookie,
                "Content-Type": "application/x-www-form-urlencoded",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.REFRESH_COOKIE_URL, data=data, headers=headers, timeout=10
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        if result.get("code") == 0:
                            data = result.get("data", {})
                            new_refresh_token = data.get("refresh_token")

                            # 从响应头中获取新Cookie
                            new_cookie = self._merge_cookies(old_cookie, resp.cookies)

                            logger.info("Cookie刷新成功")
                            return new_cookie, new_refresh_token
                        else:
                            logger.error(
                                f"刷新Cookie失败: {result.get('message')}"
                            )
                    else:
                        logger.error(f"刷新Cookie失败，HTTP状态码: {resp.status}")

        except Exception as e:
            logger.error(f"刷新Cookie时出错: {e}", exc_info=True)

        return None

    async def confirm_refresh(self, new_cookie: str, old_refresh_token: str) -> bool:
        """
        确认Cookie刷新

        Args:
            new_cookie: 新Cookie
            old_refresh_token: 旧的refresh_token

        Returns:
            是否成功
        """
        try:
            csrf = self._extract_bili_jct(new_cookie)
            if not csrf:
                logger.error("无法从新Cookie中提取bili_jct")
                return False

            data = {
                "csrf": csrf,
                "refresh_token": old_refresh_token,
            }

            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
                "Cookie": new_cookie,
                "Content-Type": "application/x-www-form-urlencoded",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.CONFIRM_REFRESH_URL, data=data, headers=headers, timeout=10
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        if result.get("code") == 0:
                            logger.info("确认Cookie刷新成功")
                            return True
                        else:
                            logger.error(f"确认刷新失败: {result.get('message')}")
                    else:
                        logger.error(f"确认刷新失败，HTTP状态码: {resp.status}")

        except Exception as e:
            logger.error(f"确认刷新时出错: {e}")

        return False

    async def auto_refresh_if_needed(self, current_cookie: str) -> Tuple[str, bool]:
        """
        自动检查并刷新Cookie（如果需要）

        Args:
            current_cookie: 当前Cookie

        Returns:
            (新Cookie或原Cookie, 是否刷新成功)
        """
        try:
            # 检查是否有 refresh_token，没有则直接返回
            refresh_token = self.get_refresh_token()
            if not refresh_token:
                logger.debug("未配置 refresh_token，跳过 Cookie 自动刷新")
                logger.debug("如需启用自动刷新，请运行: python scripts/set_refresh_token.py")
                return current_cookie, False

            # 检查今天是否已经检查过
            last_check = self.auth_data.get("last_check_time", 0)
            current_time = time.time()

            # 如果距离上次检查不到1小时，跳过
            if current_time - last_check < 3600:
                logger.debug("Cookie最近已检查，跳过")
                return current_cookie, False

            # 检查是否需要刷新
            need_refresh, timestamp = await self.check_need_refresh(current_cookie)

            # 更新检查时间
            self.auth_data["last_check_time"] = current_time
            self._save_auth_data()

            if not need_refresh:
                logger.info("Cookie无需刷新")
                return current_cookie, False

            # 需要刷新
            logger.info("检测到Cookie需要刷新，开始刷新流程...")

            # 步骤1: 生成 CorrespondPath（RSA-OAEP 加密）
            correspond_path = self._generate_correspond_path(timestamp)
            if not correspond_path:
                logger.error("生成 CorrespondPath 失败，无法继续刷新")
                logger.info("提示：可能需要手动更新 Cookie")
                return current_cookie, False

            # 步骤2: 尝试获取 refresh_csrf，如果失败则降级使用 correspond_path
            refresh_csrf = await self.get_refresh_csrf(correspond_path, current_cookie)
            if not refresh_csrf:
                logger.warning("获取 refresh_csrf 失败，尝试降级方案（直接使用 correspond_path）")
                refresh_csrf = correspond_path

            # 保存旧的refresh_token用于确认
            old_refresh_token = refresh_token

            # 步骤3: 刷新Cookie
            refresh_result = await self.refresh_cookie(current_cookie, refresh_csrf)
            if not refresh_result:
                logger.error("Cookie刷新失败")
                logger.info("提示：refresh_token 可能已失效，需要重新获取")
                return current_cookie, False

            new_cookie, new_refresh_token = refresh_result

            # 步骤4: 确认刷新
            confirmed = await self.confirm_refresh(new_cookie, old_refresh_token)
            if not confirmed:
                logger.warning("确认刷新失败，但Cookie可能已更新")

            # 步骤5: SSO 跨域登录
            logger.info("开始 SSO 跨域登录...")
            await self.sso_cross_domain_login(new_cookie)

            # 更新refresh_token（同时保存到 .env 和 auth_data）
            self.set_refresh_token(new_refresh_token, save_to_env=True)

            # 解析新Cookie并更新到 .env
            cookie_dict = self.parse_cookie_to_dict(new_cookie)
            env_updates = {}

            # 更新关键Cookie字段
            for key in ["SESSDATA", "bili_jct", "buvid3", "DedeUserID", "DedeUserID__ckMd5"]:
                if key in cookie_dict:
                    env_updates[key] = cookie_dict[key]

            if env_updates:
                self._update_env_file(env_updates)

            logger.info("Cookie自动刷新完成！")
            return new_cookie, True

        except Exception as e:
            logger.error(f"自动刷新Cookie时出错: {e}", exc_info=True)
            return current_cookie, False

    @staticmethod
    def _extract_bili_jct(cookie: str) -> Optional[str]:
        """从Cookie字符串中提取bili_jct"""
        for item in cookie.split(";"):
            item = item.strip()
            if item.startswith("bili_jct="):
                return item.split("=", 1)[1]
        return None

    @staticmethod
    def _merge_cookies(old_cookie: str, new_cookies) -> str:
        """合并旧Cookie和新Cookie"""
        # 解析旧Cookie
        cookie_dict = {}
        for item in old_cookie.split(";"):
            item = item.strip()
            if "=" in item:
                key, value = item.split("=", 1)
                cookie_dict[key] = value

        # 更新新Cookie
        for key, morsel in new_cookies.items():
            cookie_dict[key] = morsel.value

        # 重新组装
        return "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])

    def _generate_correspond_path(self, timestamp: Optional[int] = None) -> Optional[str]:
        """
        生成 CorrespondPath（使用 RSA-OAEP 加密）

        Args:
            timestamp: 毫秒时间戳

        Returns:
            CorrespondPath 字符串或 None
        """
        if not HAS_CRYPTO:
            logger.error("缺少 pycryptodome 库，请安装: pip install pycryptodome")
            return None

        if timestamp is None:
            timestamp = int(time.time() * 1000)

        try:
            # 导入公钥
            key = RSA.importKey(self.BILIBILI_PUBLIC_KEY)

            # 使用 RSA-OAEP 加密，使用 SHA256
            cipher = PKCS1_OAEP.new(key, SHA256)
            message = f"refresh_{timestamp}".encode()
            encrypted = cipher.encrypt(message)

            # 转换为十六进制字符串
            correspond_path = binascii.b2a_hex(encrypted).decode()

            logger.debug(f"生成 CorrespondPath 成功: timestamp={timestamp}")
            return correspond_path

        except Exception as e:
            logger.error(f"生成 CorrespondPath 失败: {e}", exc_info=True)
            return None


# 全局认证管理器实例
_auth_instance: Optional[BilibiliAuth] = None


def get_auth_manager() -> BilibiliAuth:
    """获取全局认证管理器实例"""
    global _auth_instance
    if _auth_instance is None:
        _auth_instance = BilibiliAuth()
    return _auth_instance
