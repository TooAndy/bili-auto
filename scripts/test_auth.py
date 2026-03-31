#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 B站 Cookie 刷新流程

使用方法:
    python scripts/test_auth.py          # 完整测试流程
    python scripts/test_auth.py --step   # 分步测试
    python scripts/test_auth.py --correspond  # 仅测试 CorrespondPath 生成
"""

import sys
import asyncio
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.modules.bilibili_auth import get_auth_manager, HAS_CRYPTO
from config import Config


def print_separator(title=""):
    """打印分隔线"""
    print("\n" + "=" * 70)
    if title:
        print(f"  {title}")
        print("=" * 70)


async def test_correspond_path():
    """测试 CorrespondPath 生成"""
    print_separator("测试 1: CorrespondPath 生成")

    if not HAS_CRYPTO:
        print("❌ 缺少 pycryptodome 库")
        print("   请运行: pip install pycryptodome")
        return False

    auth = get_auth_manager()

    # 测试生成
    import time
    timestamp = int(time.time() * 1000)
    correspond_path = auth._generate_correspond_path(timestamp)

    if correspond_path:
        print(f"✅ 生成成功")
        print(f"   时间戳: {timestamp}")
        print(f"   CorrespondPath: {correspond_path[:60]}...")
        print(f"   长度: {len(correspond_path)} 字符")
        return True
    else:
        print("❌ 生成失败")
        return False


async def test_check_cookie():
    """测试 Cookie 检查"""
    print_separator("测试 2: Cookie 状态检查")

    if not Config.BILIBILI_COOKIE:
        print("❌ 未配置 BILIBILI_COOKIE")
        print("   请在 .env 文件中设置 BILIBILI_COOKIE")
        return False

    auth = get_auth_manager()
    need_refresh, timestamp = await auth.check_need_refresh(Config.BILIBILI_COOKIE)

    print(f"✅ 检查完成")
    print(f"   需要刷新: {need_refresh}")
    print(f"   时间戳: {timestamp}")
    return True


async def test_get_refresh_csrf():
    """测试获取 refresh_csrf"""
    print_separator("测试 3: 获取 refresh_csrf")

    if not Config.BILIBILI_COOKIE:
        print("❌ 未配置 BILIBILI_COOKIE")
        return False

    auth = get_auth_manager()

    # 先生成 CorrespondPath
    import time
    timestamp = int(time.time() * 1000)
    correspond_path = auth._generate_correspond_path(timestamp)

    if not correspond_path:
        print("❌ 生成 CorrespondPath 失败")
        return False

    print(f"   CorrespondPath 生成成功")

    # 获取 refresh_csrf
    refresh_csrf = await auth.get_refresh_csrf(correspond_path, Config.BILIBILI_COOKIE)

    if refresh_csrf:
        print(f"✅ 获取 refresh_csrf 成功")
        print(f"   refresh_csrf: {refresh_csrf[:50]}...")
        return True
    else:
        print("❌ 获取 refresh_csrf 失败")
        return False


async def test_full_flow(confirm=False):
    """完整测试流程"""
    print_separator("完整测试: Cookie 自动刷新流程")

    if not Config.BILIBILI_COOKIE:
        print("❌ 未配置 BILIBILI_COOKIE")
        return False

    auth = get_auth_manager()
    refresh_token = auth.get_refresh_token()

    if not refresh_token:
        print("❌ 未配置 refresh_token")
        print("   请运行: python scripts/set_refresh_token.py")
        return False

    print(f"✅ 配置检查通过")
    print(f"   Cookie 已配置")
    print(f"   refresh_token: {refresh_token[:30]}...")

    # 先检查是否需要刷新
    need_refresh, timestamp = await auth.check_need_refresh(Config.BILIBILI_COOKIE)

    if not need_refresh:
        print("\nℹ️  当前 Cookie 不需要刷新")
        print("   如需测试完整流程，可以等待 Cookie 接近过期")
        print("   或者修改 last_check_time 来强制检测")

        if confirm:
            resp = input("\n是否继续测试（不会实际刷新）? (y/N): ").strip().lower()
            if resp != "y":
                return True

        print("\n🧪 测试各个步骤（不实际刷新）:")

        # 测试 CorrespondPath 生成
        print("\n1️⃣  测试 CorrespondPath 生成...")
        auth = get_auth_manager()
        correspond_path = auth._generate_correspond_path(timestamp)
        if correspond_path:
            print("   ✅ 成功")
        else:
            print("   ❌ 失败")
            return False

        # 测试获取 refresh_csrf
        print("\n2️⃣  测试获取 refresh_csrf...")
        refresh_csrf = await auth.get_refresh_csrf(correspond_path, Config.BILIBILI_COOKIE)
        if refresh_csrf:
            print("   ✅ 成功")
        else:
            print("   ❌ 失败")
            return False

        print("\n🎉 所有步骤测试通过！")
        return True
    else:
        print("\n⚠️  检测到 Cookie 需要刷新！")
        print("   继续将执行实际的刷新操作")

        if not confirm:
            resp = input("\n是否继续? (y/N): ").strip().lower()
            if resp != "y":
                print("已取消")
                return True

        print("\n🚀 开始刷新流程...")
        new_cookie, refreshed = await auth.auto_refresh_if_needed(Config.BILIBILI_COOKIE)

        if refreshed:
            print("\n🎉 Cookie 刷新成功！")
            print("   新 Cookie 和 refresh_token 已保存到 .env")
            return True
        else:
            print("\n❌ Cookie 刷新失败")
            return False


def check_env():
    """检查环境配置"""
    print_separator("环境检查")

    print(f"pycryptodome: {'✅ 已安装' if HAS_CRYPTO else '❌ 未安装'}")
    print(f"BILIBILI_COOKIE: {'✅ 已配置' if Config.BILIBILI_COOKIE else '❌ 未配置'}")

    auth = get_auth_manager()
    refresh_token = auth.get_refresh_token()
    print(f"refresh_token: {'✅ 已配置' if refresh_token else '❌ 未配置'}")

    return HAS_CRYPTO and Config.BILIBILI_COOKIE and refresh_token


async def main():
    parser = argparse.ArgumentParser(description="测试 B站 Cookie 刷新流程")
    parser.add_argument("--correspond", action="store_true", help="仅测试 CorrespondPath 生成")
    parser.add_argument("--step", action="store_true", help="分步测试")
    parser.add_argument("--yes", action="store_true", help="跳过确认")
    args = parser.parse_args()

    print("\n🧪 B站 Cookie 刷新流程测试")

    # 环境检查
    env_ok = check_env()

    if args.correspond:
        await test_correspond_path()
    elif args.step:
        if not env_ok:
            print("\n❌ 环境不完整，请先配置")
            return
        await test_correspond_path()
        await test_check_cookie()
        await test_get_refresh_csrf()
    else:
        if not env_ok:
            print("\n❌ 环境不完整，请先配置")
            print("\n配置步骤:")
            print("  1. 安装依赖: pip install pycryptodome")
            print("  2. 在 .env 中配置 BILIBILI_COOKIE")
            print("  3. 运行: python scripts/set_refresh_token.py")
            return
        await test_full_flow(confirm=args.yes)

    print_separator()
    print("测试完成")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n已取消")
        sys.exit(0)
