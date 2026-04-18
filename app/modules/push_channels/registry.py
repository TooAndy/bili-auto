from typing import Dict, Type, List, Optional
from app.modules.push_channels.base import BaseChannel


class ChannelRegistry:
    """推送渠道注册表"""

    _channels: Dict[str, Type[BaseChannel]] = {}
    _instances: Dict[str, BaseChannel] = {}

    @classmethod
    def register(cls, channel_class: Type[BaseChannel]) -> Type[BaseChannel]:
        """注册渠道类"""
        instance = channel_class()
        cls._channels[instance.channel_name] = channel_class
        cls._instances[instance.channel_name] = instance
        return channel_class

    @classmethod
    def get(cls, channel_name: str) -> Optional[BaseChannel]:
        """获取渠道实例"""
        return cls._instances.get(channel_name)

    @classmethod
    def list_channels(cls) -> List[str]:
        """列出所有已注册的渠道"""
        return list(cls._channels.keys())

    @classmethod
    def send_to_channel(cls, channel_name: str, content_data: dict) -> bool:
        """向指定渠道发送内容"""
        channel = cls.get(channel_name)
        if not channel:
            return False
        return channel.send(content_data)

    @classmethod
    def send_to_channels(cls, channel_names: List[str], content_data: dict) -> bool:
        """向多个渠道发送内容"""
        success = True
        for name in channel_names:
            if not cls.send_to_channel(name, content_data):
                success = False
        return success


def get_channel(channel_name: str) -> Optional[BaseChannel]:
    """获取渠道实例"""
    return ChannelRegistry.get(channel_name)


def list_channels() -> List[str]:
    """列出所有已注册的渠道"""
    return ChannelRegistry.list_channels()


def send_to_channel(channel_name: str, content_data: dict) -> bool:
    """向指定渠道发送内容"""
    return ChannelRegistry.send_to_channel(channel_name, content_data)


def send_to_channels(channel_names: List[str], content_data: dict) -> bool:
    """向多个渠道发送内容"""
    return ChannelRegistry.send_to_channels(channel_names, content_data)
