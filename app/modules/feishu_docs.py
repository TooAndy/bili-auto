#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书文档 API 封装模块
用于创建和更新飞书文档，支持 Markdown 内容
"""

import json
import re
import requests
from typing import Optional, Dict, Any
from datetime import datetime
from app.utils.logger import get_logger
from config import Config

logger = get_logger("feishu_docs")


def _simple_markdown_to_blocks(markdown: str) -> list:
    """
    简单的 Markdown 到飞书文档块的转换
    支持基本的标题、段落、列表等

    Args:
        markdown: Markdown 文本

    Returns:
        飞书文档块列表
    """
    blocks = []
    lines = markdown.split("\n")

    for line in lines:
        line = line.rstrip()
        if not line:
            continue

        # 标题
        if line.startswith("# "):
            blocks.append({
                "block_type": 2,  # heading1
                "heading1": {
                    "elements": [{
                        "text_run": {
                            "content": line[2:].strip()
                        }
                    }]
                }
            })
        elif line.startswith("## "):
            blocks.append({
                "block_type": 3,  # heading2
                "heading2": {
                    "elements": [{
                        "text_run": {
                            "content": line[3:].strip()
                        }
                    }]
                }
            })
        elif line.startswith("### "):
            blocks.append({
                "block_type": 4,  # heading3
                "heading3": {
                    "elements": [{
                        "text_run": {
                            "content": line[4:].strip()
                        }
                    }]
                }
            })
        # 分隔线
        elif line.strip() == "---":
            blocks.append({
                "block_type": 19,  # divider
                "divider": {}
            })
        # 列表项
        elif line.startswith("- "):
            blocks.append({
                "block_type": 7,  # bullet
                "bullet": {
                    "elements": [{
                        "text_run": {
                            "content": line[2:].strip()
                        }
                    }]
                }
            })
        # 粗体
        elif line.startswith("**") and line.endswith("**"):
            content = line[2:-2].strip()
            blocks.append({
                "block_type": 1,  # text
                "text": {
                    "style": {"bold": True},
                    "elements": [{
                        "text_run": {
                            "content": content
                        }
                    }]
                }
            })
        # 普通段落
        else:
            blocks.append({
                "block_type": 1,  # text
                "text": {
                    "elements": [{
                        "text_run": {
                            "content": line
                        }
                    }]
                }
            })

    return blocks


def create_doc_from_markdown(
    title: str,
    markdown_content: str,
    folder_token: Optional[str] = None,
    space_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    从 Markdown 内容创建飞书文档

    Args:
        title: 文档标题
        markdown_content: Markdown 内容
        folder_token: 文件夹 token（可选）
        space_id: 知识空间 id（可选）

    Returns:
        创建成功返回文档信息，失败返回 None
        {
            "doc_token": "文档token",
            "url": "文档链接",
            "title": "文档标题"
        }
    """
    from app.modules.push import get_feishu_tenant_access_token

    token = get_feishu_tenant_access_token()
    if not token:
        logger.error("无法获取飞书 access_token")
        return None

    # 构建文档内容块
    blocks = _simple_markdown_to_blocks(markdown_content)

    # 构建请求体
    payload = {
        "title": title,
        "children": blocks
    }

    # 如果指定了文件夹，添加到请求中
    if folder_token:
        payload["folder_token"] = folder_token

    url = "https://open.feishu.cn/open-apis/docx/v1/documents"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        data = resp.json()

        if data.get("code") == 0:
            doc_data = data.get("data", {}).get("document", {})
            doc_token = doc_data.get("document_id", "")
            doc_url = f"https://bytedance.feishu.cn/docx/{doc_token}"

            result = {
                "doc_token": doc_token,
                "url": doc_url,
                "title": doc_data.get("title", title)
            }
            logger.info("飞书文档创建成功: %s", doc_url)
            return result
        else:
            logger.error("飞书文档创建失败: code=%s, msg=%s", data.get("code"), data.get("msg"))
            return None

    except Exception as e:
        logger.error("飞书文档创建异常: %s", e, exc_info=True)
        return None


def create_doc_simple(
    title: str,
    content: str,
    folder_token: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    简单创建文档：将内容作为纯文本上传（兼容性更好）

    Args:
        title: 文档标题
        content: 文档内容
        folder_token: 文件夹 token（可选）

    Returns:
        创建成功返回文档信息，失败返回 None
    """
    from app.modules.push import get_feishu_tenant_access_token

    token = get_feishu_tenant_access_token()
    if not token:
        logger.error("无法获取飞书 access_token")
        return None

    # 先创建一个空文档
    payload = {"title": title}
    if folder_token:
        payload["folder_token"] = folder_token

    url = "https://open.feishu.cn/open-apis/docx/v1/documents"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }

    try:
        # 第一步：创建文档
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        data = resp.json()

        if data.get("code") != 0:
            logger.error("飞书文档创建失败: code=%s, msg=%s", data.get("code"), data.get("msg"))
            return None

        doc_data = data.get("data", {}).get("document", {})
        doc_token = doc_data.get("document_id", "")
        doc_url = f"https://bytedance.feishu.cn/docx/{doc_token}"

        # 第二步：使用旧版文档 API 上传内容（更稳定）
        # 先尝试获取文档的 block_id
        old_doc_url = f"https://open.feishu.cn/open-apis/doc/v2/content/{doc_token}"
        old_resp = requests.get(old_doc_url, headers=headers, timeout=30)

        if old_resp.status_code == 200:
            # 尝试使用旧版 API 更新内容
            update_url = f"https://open.feishu.cn/open-apis/doc/v2/content/{doc_token}"
            update_payload = {
                "content": content,
                "resolve_image": False
            }
            update_resp = requests.post(update_url, headers=headers, json=update_payload, timeout=30)
            if update_resp.status_code == 200:
                logger.info("飞书文档内容更新成功（旧版API）: %s", doc_url)

        result = {
            "doc_token": doc_token,
            "url": doc_url,
            "title": doc_data.get("title", title)
        }
        logger.info("飞书文档创建成功: %s", doc_url)
        return result

    except Exception as e:
        logger.error("飞书文档创建异常: %s", e, exc_info=True)
        return None


def push_video_summary_to_doc(
    title: str,
    markdown_content: str,
    bvid: str,
    uploader_name: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    将视频 summary 推送到飞书文档

    Args:
        title: 文档标题（通常是视频标题）
        markdown_content: summary.md 的内容
        bvid: 视频 BV 号
        uploader_name: UP 主名称（可选，用于文件夹组织）

    Returns:
        成功返回文档信息，失败返回 None
    """
    if not Config.FEISHU_DOCS_ENABLED:
        logger.debug("飞书文档功能未启用")
        return None

    # 构建完整标题，加上日期前缀
    now = datetime.now()
    date_prefix = now.strftime("%Y%m%d")
    full_title = f"{date_prefix}_{bvid}_{title[:50]}"

    folder_token = Config.FEISHU_DOCS_FOLDER_TOKEN

    # 尝试创建文档 - 先用简单方式
    result = create_doc_simple(full_title, markdown_content, folder_token)

    if not result:
        logger.warning("简单方式创建失败，尝试 Markdown 方式...")
        result = create_doc_from_markdown(full_title, markdown_content, folder_token)

    return result
