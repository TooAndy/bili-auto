#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书文档 API 封装模块
用于将 Markdown 文件上传到飞书云盘
"""

import io
import requests
from typing import Optional, Dict, Any
from datetime import datetime
from app.utils.logger import get_logger
from config import Config

logger = get_logger("feishu_docs")


def upload_markdown_to_feishu(
    title: str,
    markdown_content: str,
    folder_token: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    将 Markdown 内容上传到飞书云盘

    Args:
        title: 文件标题
        markdown_content: Markdown 内容
        folder_token: 文件夹 token（可选）

    Returns:
        成功返回文件信息，失败返回 None
        {
            "file_token": "文件token",
            "url": "文件链接",
            "name": "文件名"
        }
    """
    from app.modules.push import get_feishu_tenant_access_token

    token = get_feishu_tenant_access_token()
    if not token:
        logger.error("无法获取飞书 access_token")
        return None

    # 构建文件名
    file_name = f"{title}.md"
    content_bytes = markdown_content.encode("utf-8")
    file_size = len(content_bytes)

    headers = {
        "Authorization": f"Bearer {token}"
    }

    # 构建请求参数
    payload = {
        "file_name": file_name,
        "parent_type": "explorer",
        "size": file_size
    }

    if folder_token:
        payload["parent_node"] = folder_token

    try:
        # 使用 multipart/form-data 上传文件
        files = {
            "file": (file_name, io.BytesIO(content_bytes), "text/markdown")
        }

        url = "https://open.feishu.cn/open-apis/drive/v1/files/upload_all"
        resp = requests.post(
            url,
            headers=headers,
            data=payload,
            files=files,
            timeout=60
        )

        data = resp.json()
        logger.debug("上传响应: %s", data)

        if data.get("code") == 0:
            file_data = data.get("data", {})
            file_token = file_data.get("file_token", "")
            file_url = f"https://bytedance.feishu.cn/file/{file_token}"

            result = {
                "file_token": file_token,
                "url": file_url,
                "name": file_name
            }
            logger.info("飞书文件上传成功: %s", file_url)
            return result
        else:
            logger.error("飞书文件上传失败: code=%s, msg=%s", data.get("code"), data.get("msg"))
            return None

    except Exception as e:
        logger.error("飞书文件上传异常: %s", e, exc_info=True)
        return None


def push_video_summary_to_doc(
    title: str,
    markdown_content: str,
    bvid: str,
    uploader_name: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    将视频 summary 上传到飞书云盘

    Args:
        title: 文档标题（通常是视频标题）
        markdown_content: summary.md 的内容
        bvid: 视频 BV 号
        uploader_name: UP 主名称（可选）

    Returns:
        成功返回文件信息，失败返回 None
    """
    if not Config.FEISHU_DOCS_ENABLED:
        logger.debug("飞书文档功能未启用")
        return None

    # 构建完整标题，加上日期前缀
    now = datetime.now()
    date_prefix = now.strftime("%Y%m%d")
    full_title = f"{date_prefix}_{bvid}_{title[:50]}"

    folder_token = Config.FEISHU_DOCS_FOLDER_TOKEN

    result = upload_markdown_to_feishu(full_title, markdown_content, folder_token)

    return result