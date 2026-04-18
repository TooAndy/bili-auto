"""
推送渠道模块

插件化架构，每个渠道独立实现，方便扩展。

已注册渠道:
- feishu: 飞书
- wechat: 微信企业号
- telegram: Telegram

使用方式:
    from app.modules.push_channels import push_content, list_channels

    push_content({"type": "dynamic", "text": "内容", ...}, ["feishu", "telegram"])
"""

# 导入各渠道模块，触发注册
from app.modules.push_channels import feishu  # noqa: F401
from app.modules.push_channels import wechat  # noqa: F401
from app.modules.push_channels import telegram  # noqa: F401

# 导入核心函数
from app.modules.push_channels.registry import (
    get_channel,
    list_channels,
    send_to_channel,
    send_to_channels,
)


def push_content(content_data: dict, channels: list) -> bool:
    """
    统一推送接口

    Args:
        content_data: 内容数据
            - type: "video" | "dynamic"
            - title/text: 标题或文本
            - summary: 摘要（仅视频）
            - url: 链接
            - images: 本地图片路径列表
            - image_urls: 图片URL列表
            - pub_time: 发布时间字符串
            - tags: 标签列表
            - stocks: 股票列表
        channels: 渠道列表，如 ["feishu", "wechat", "telegram"]

    Returns:
        bool: 是否全部发送成功
    """
    from app.utils.logger import get_logger

    logger = get_logger("push")
    content_type = content_data.get("type", "unknown")

    success = True

    for channel_name in channels:
        channel = get_channel(channel_name)
        if not channel:
            logger.warning("未知的推送渠道: %s", channel_name)
            success = False
            continue

        try:
            if channel.send(content_data):
                logger.debug("[%s] 推送成功", channel_name)
            else:
                logger.warning("[%s] 推送失败", channel_name)
                success = False
        except Exception as e:
            logger.error("[%s] 推送异常: %s", channel_name, e)
            success = False

    # 记录日志
    if content_type == "video":
        logger.info(
            "[推送] 视频: %s | 标题: %s | 渠道: %s",
            content_data.get("url", ""),
            content_data.get("title", "")[:50],
            channels,
        )
    elif content_type == "dynamic":
        logger.info(
            "[推送] 动态: %s | 内容: %s | 渠道: %s",
            content_data.get("url", ""),
            content_data.get("text", "")[:50],
            channels,
        )

    return success


# 保持向后兼容
def push_video_to_feishu(content_data: dict) -> bool:
    """推送视频到飞书（兼容旧接口）"""
    channel = get_channel("feishu")
    if channel:
        return channel.send({**content_data, "type": "video"})
    return False


def push_dynamic_to_feishu(content_data: dict) -> bool:
    """推送动态到飞书（兼容旧接口）"""
    channel = get_channel("feishu")
    if channel:
        return channel.send({**content_data, "type": "dynamic"})
    return False
