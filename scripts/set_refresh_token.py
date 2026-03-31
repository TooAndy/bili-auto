#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
手动设置 refresh_token 工具

当无法使用二维码登录时，可以从浏览器手动获取 refresh_token
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def update_env_file(refresh_token: str) -> bool:
    """
    更新 .env 文件中的 refresh_token

    Args:
        refresh_token: 从浏览器获取的 refresh_token

    Returns:
        是否成功
    """
    try:
        env_file = Path(__file__).parent.parent / ".env"

        # 读取现有配置
        env_lines = []
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                env_lines = f.readlines()

        # 查找并更新 refresh_token
        found = False
        for i, line in enumerate(env_lines):
            if line.startswith("refresh_token="):
                env_lines[i] = f"refresh_token={refresh_token}\n"
                found = True
                break

        # 如果没找到，添加到末尾
        if not found:
            env_lines.append("\n# B站 refresh_token（用于 Cookie 自动刷新）\n")
            env_lines.append("# 获取方法见下文\n")
            env_lines.append(f"refresh_token={refresh_token}\n")

        # 写回文件
        with open(env_file, "w", encoding="utf-8") as f:
            f.writelines(env_lines)

        print(f"[OK] refresh_token 已保存到: {env_file}")
        return True

    except Exception as e:
        print(f"[ERROR] 保存失败: {e}")
        return False


def main():
    """主函数"""
    print("=" * 70)
    print("手动设置 refresh_token - B站 Cookie 自动刷新")
    print("=" * 70)

    print("\n📝 如何从浏览器获取 refresh_token:")
    print("-" * 70)
    print("\n【推荐方法】从登录请求中获取（成功率最高）")
    print("1. 打开浏览器无痕/隐私模式")
    print("2. 访问: https://passport.bilibili.com/login")
    print("3. 按 F12 打开开发者工具，切换到 [Network] 标签")
    print("4. 点击过滤器，选择 [Fetch/XHR]")
    print("5. 完成登录（扫码或密码登录）")
    print("6. 在 Network 中查找名称包含 'login' 或 'web' 的请求")
    print("7. 查看 Response，找到 refresh_token 字段")
    print("   通常在 /x/passport-login/web/login 的响应中")

    print("\n方法 2: 从 localStorage 获取")
    print("1. 在已登录的B站页面，按 F12 打开开发者工具")
    print("2. 切换到 [Console] 控制台")
    print("3. 依次尝试以下命令:")
    print("   localStorage.getItem('ac_time_value')")
    print("   localStorage.getItem('refresh_token')")
    print("   JSON.parse(localStorage.getItem('bili_ticket') || '{}')")
    print("4. 如果输出是字符串，复制它（不包括引号）")

    print("\n方法 3: 从 Application 面板查找")
    print("1. 在已登录的B站页面，按 F12 打开开发者工具")
    print("2. 切换到 [Application] 标签")
    print("3. 左侧选择 [Local Storage] -> https://www.bilibili.com")
    print("4. 查找以下键:")
    print("   - ac_time_value")
    print("   - refresh_token")
    print("   - bili_ticket")
    print("5. 复制对应的值")

    print("\n方法 4: 从 Cookie 中查找")
    print("1. 在已登录的B站页面，按 F12 打开开发者工具")
    print("2. 切换到 [Application] -> [Cookies] -> https://www.bilibili.com")
    print("3. 查找 ac_time_value 字段")

    print("\n💡 提示:")
    print("- 如果以上方法都找不到，说明你当前的登录会话没有 refresh_token")
    print("- 建议退出登录，重新登录一次（使用无痕模式）")
    print("- 使用扫码登录比密码登录更容易获取到 refresh_token")
    print("- 如果仍然无法获取，可以暂时不配置 refresh_token，系统仍能正常工作")
    print("  只是 Cookie 过期后需要手动重新获取 Cookie")

    print("\n" + "-" * 70)

    # 获取用户输入
    print("\n请粘贴你的 refresh_token (直接回车跳过):")
    print("（提示：通常是一串很长的字符串，如：c12a1234567890abcdef...）")
    print()

    refresh_token = input("refresh_token: ").strip()

    if not refresh_token:
        print("\n[INFO] 已跳过，未设置 refresh_token")
        print("\n你可以稍后再运行此脚本设置")
        print("即使没有 refresh_token，系统仍能正常工作（仅无法自动刷新 Cookie）")
        return 0

    if len(refresh_token) < 20:
        print("\n[WARNING] refresh_token 长度似乎太短，请确认是否正确")
        confirm = input("是否继续保存？(y/N): ").strip().lower()
        if confirm != "y":
            print("[INFO] 已取消")
            return 0

    # 保存到 .env
    print("\n保存中...")
    if update_env_file(refresh_token):
        print("\n" + "=" * 70)
        print("[SUCCESS] 设置完成！")
        print("=" * 70)
        print("\n✅ refresh_token 已保存到 .env 文件")
        print("✅ Cookie 自动刷新功能已启用")
        print("\n📖 使用说明:")
        print("1. 系统将在每次启动时检查 Cookie 有效期")
        print("2. 当 Cookie 需要刷新时，系统会自动使用 refresh_token 更新")
        print("3. 新的 Cookie 和 refresh_token 会自动保存回 .env 文件")
        print("\n💡 提示：无需手动更新 Cookie，系统会自动维护！")
        return 0
    else:
        print("\n[ERROR] 设置失败，请检查错误信息")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n[INFO] 用户取消操作")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] 发生错误: {e}")
        sys.exit(1)
