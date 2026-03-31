# -*- coding: utf-8 -*-
"""
B站认证和Cookie管理模块

实现B站Cookie自动刷新机制
参考文档: https://socialsisteryi.github.io/bilibili-API-collect/docs/login/cookie_refresh.html
"""

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional, Tuple

import aiohttp

from app.utils.logger import get_logger

logger = get_logger("bilibili_auth")


class BilibiliAuth:
    """B站认证管理类"""

    # API端点
    CHECK_COOKIE_URL = "https://passport.bilibili.com/x/passport-login/web/cookie/info"
    REFRESH_COOKIE_URL = (
        "https://passport.bilibili.com/x/passport-login/web/cookie/refresh"
    )
    CONFIRM_REFRESH_URL = (
        "https://passport.bilibili.com/x/passport-login/web/confirm/refresh"
    )

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

    async def refresh_cookie(
        self, old_cookie: str, correspond_path: str
    ) -> Optional[Tuple[str, str]]:
        """
        刷新Cookie

        Args:
            old_cookie: 旧Cookie
            correspond_path: CorrespondPath（由时间戳生成）

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
                "refresh_csrf": correspond_path,
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

            # 生成CorrespondPath（简化版，实际应该使用wasm算法）
            correspond_path = self._generate_correspond_path(timestamp)

            # 保存旧的refresh_token用于确认
            old_refresh_token = self.get_refresh_token()
            if not old_refresh_token:
                logger.error("没有refresh_token，无法刷新")
                return current_cookie, False

            # 刷新Cookie
            refresh_result = await self.refresh_cookie(current_cookie, correspond_path)
            if not refresh_result:
                logger.error("Cookie刷新失败")
                return current_cookie, False

            new_cookie, new_refresh_token = refresh_result

            # 确认刷新
            confirmed = await self.confirm_refresh(new_cookie, old_refresh_token)
            if not confirmed:
                logger.warning("确认刷新失败，但Cookie可能已更新")

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

    @staticmethod
    def _generate_correspond_path(timestamp: Optional[int] = None) -> str:
        """
        生成CorrespondPath

        注意：这是简化版本，完整实现需要使用B站的wasm算法
        文档中的wasm文件：https://s1.hdslb.com/bfs/static/jinkela/long/wasm/wasm_rsa_encrypt_bg.wasm

        Args:
            timestamp: 毫秒时间戳

        Returns:
            CorrespondPath字符串
        """
        if timestamp is None:
            timestamp = int(time.time() * 1000)

        # 简化版本：使用时间戳的十六进制
        # 实际应该调用wasm算法
        return hex(timestamp)[2:]


# 全局认证管理器实例
_auth_instance: Optional[BilibiliAuth] = None


def get_auth_manager() -> BilibiliAuth:
    """获取全局认证管理器实例"""
    global _auth_instance
    if _auth_instance is None:
        _auth_instance = BilibiliAuth()
    return _auth_instance
