"""
推送模块 - 兼容旧接口

新接口请使用 app.modules.push_channels:
    from app.modules.push_channels import push_content, list_channels
"""

# 重新导出新接口，保持向后兼容
from app.modules.push_channels import (
    push_content,
    list_channels,
    get_channel,
    send_to_channel,
    send_to_channels,
)

# 从飞书渠道导出辅助函数（供 feishu_docs.py 使用）
from app.modules.push_channels.feishu import get_feishu_tenant_access_token

# 保留原有函数作为别名（兼容旧代码）
push_feishu_text = lambda text: get_channel("feishu").send_text(text) if get_channel("feishu") else False
