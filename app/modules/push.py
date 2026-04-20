"""
推送模块 - 兼容旧接口

新接口请使用 app.modules.push_channels:
    from app.modules.push_channels import push_content, list_channels
"""

# 重新导出新接口，保持向后兼容
from app.modules.push_channels import (  # noqa: F401
    push_content,
    list_channels,
    get_channel,
    get_enabled_channels,
)

# 从飞书渠道导出辅助函数（供 feishu_docs.py 使用）
from app.modules.push_channels.feishu import get_feishu_tenant_access_token  # noqa: F401

# 保留原有函数作为别名（兼容旧代码）
def _push_feishu_text(text: str) -> bool:
    channel = get_channel("feishu")
    return channel.send_text(text) if channel else False


push_feishu_text = _push_feishu_text
