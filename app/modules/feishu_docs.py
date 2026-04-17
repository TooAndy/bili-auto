#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书文档 API 封装模块
用于将 Markdown 文件上传到飞书云盘，支持按 UP 主和内容分类
"""

import io
import re
import requests
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.utils.logger import get_logger
from config import Config

logger = get_logger("feishu_docs")


def _classify_title(uploader_name: str, title: str) -> Optional[str]:
    """
    根据标题分类

    Args:
        uploader_name: UP 主名称
        title: 视频标题

    Returns:
        匹配的分类名称，如果没有匹配返回 None
    """
    from app.models.database import SessionLocal, ClassificationRule

    session = SessionLocal()
    try:
        # 查询该 UP 主和通用（*）规则，按优先级排序
        rules = session.query(ClassificationRule).filter(
            (ClassificationRule.uploader_name == uploader_name) |
            (ClassificationRule.uploader_name == "*"),
            ClassificationRule.is_active == True
        ).order_by(ClassificationRule.priority).all()

        for rule in rules:
            try:
                if re.search(rule.pattern, title):
                    logger.debug(f"标题 '{title}' 匹配规则 '{rule.pattern}' -> '{rule.target_folder}'")
                    return rule.target_folder
            except re.error as e:
                logger.warning(f"正则表达式错误: {rule.pattern}, {e}")
                continue

        return None
    finally:
        session.close()


def _get_folder_mapping(uploader_name: str, category: str) -> Optional[str]:
    """获取已缓存的文件夹 token"""
    from app.models.database import SessionLocal, FolderMapping

    session = SessionLocal()
    try:
        mapping = session.query(FolderMapping).filter_by(
            uploader_name=uploader_name,
            category=category
        ).first()
        return mapping.folder_token if mapping else None
    finally:
        session.close()


def _save_folder_mapping(uploader_name: str, category: str, folder_token: str, folder_path: str):
    """保存文件夹映射到数据库"""
    from app.models.database import SessionLocal, FolderMapping

    session = SessionLocal()
    try:
        existing = session.query(FolderMapping).filter_by(
            uploader_name=uploader_name,
            category=category
        ).first()

        if existing:
            existing.folder_token = folder_token
            existing.folder_path = folder_path
        else:
            mapping = FolderMapping(
                uploader_name=uploader_name,
                category=category,
                folder_token=folder_token,
                folder_path=folder_path
            )
            session.add(mapping)

        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"保存文件夹映射失败: {e}")
    finally:
        session.close()


def _verify_folder_exists(folder_token: str, token: str) -> bool:
    """
    验证文件夹是否存在

    Args:
        folder_token: 文件夹 token
        token: tenant access token

    Returns:
        True 如果存在，False 否则
    """
    url = "https://open.feishu.cn/open-apis/drive/v1/files"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }

    try:
        resp = requests.get(url, headers=headers, params={"page_size": 1, "folder_token": folder_token}, timeout=30)
        data = resp.json()
        return data.get("code") == 0
    except Exception:
        return False


def _find_folder_in_feishu(parent_token: Optional[str], folder_name: str, token: str) -> Optional[str]:
    """
    在飞书中查找同名文件夹

    Args:
        parent_token: 父文件夹 token，None 表示根目录
        folder_name: 文件夹名称
        token: tenant access token

    Returns:
        文件夹 token，如果不存在返回 None
    """
    if not parent_token:
        # 如果没有指定父文件夹，无法查找（根目录不支持列出文件夹）
        return None

    url = "https://open.feishu.cn/open-apis/drive/v1/files"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }

    try:
        resp = requests.get(url, headers=headers, params={"page_size": 200, "folder_token": parent_token}, timeout=30)
        data = resp.json()

        if data.get("code") == 0:
            files = data.get("data", {}).get("files", [])
            for f in files:
                if f.get("type") == "folder" and f.get("name") == folder_name:
                    return f.get("token")
        return None
    except Exception as e:
        logger.error(f"查找文件夹异常: {e}")
        return None


def _create_or_get_folder(parent_token: Optional[str], folder_name: str, token: str) -> Optional[str]:
    """
    获取或创建文件夹

    Args:
        parent_token: 父文件夹 token，None 表示根目录
        folder_name: 文件夹名称
        token: tenant access token

    Returns:
        文件夹 token，失败返回 None
    """
    # 先查找是否已存在
    existing = _find_folder_in_feishu(parent_token, folder_name, token)
    if existing:
        logger.debug(f"文件夹已存在: {folder_name} -> {existing}")
        return existing

    # 不存在则创建
    url = "https://open.feishu.cn/open-apis/drive/v1/files/create_folder"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }

    payload = {"name": folder_name}
    if parent_token:
        payload["folder_token"] = parent_token

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        data = resp.json()

        if data.get("code") == 0:
            return data.get("data", {}).get("token")
        else:
            logger.error(f"创建文件夹失败: code={data.get('code')}, msg={data.get('msg')}")
            return None
    except Exception as e:
        logger.error(f"创建文件夹异常: {e}")
        return None


def _ensure_category_folder_exists(uploader_name: str, category: str) -> Optional[str]:
    """
    确保 UP 主的分类文件夹存在

    Args:
        uploader_name: UP 主名称
        category: 分类名称

    Returns:
        文件夹 token，失败返回 None
    """
    from app.modules.push import get_feishu_tenant_access_token

    # 1. 先检查缓存，如果缓存存在且有效就直接使用
    cached_token = _get_folder_mapping(uploader_name, category)
    if cached_token:
        logger.debug(f"使用缓存的文件夹 token: {cached_token}")
        return cached_token

    # 2. 获取 token
    token = get_feishu_tenant_access_token()
    if not token:
        logger.error("无法获取飞书 access_token")
        return None

    # 3. 获取或创建 UP 主文件夹
    uploader_folder_token = _get_folder_mapping(uploader_name, "")
    if not uploader_folder_token:
        uploader_folder_token = _create_or_get_folder(
            Config.FEISHU_DOCS_FOLDER_TOKEN if Config.FEISHU_DOCS_FOLDER_TOKEN else None,
            uploader_name,
            token
        )
        if uploader_folder_token:
            _save_folder_mapping(uploader_name, "", uploader_folder_token, uploader_name)
            logger.info(f"创建 UP 主文件夹: {uploader_name} -> {uploader_folder_token}")
    else:
        # 验证缓存的 UP 主文件夹是否仍然有效
        if not _verify_folder_exists(uploader_folder_token, token):
            logger.warning(f"缓存的 UP 主文件夹已失效，重新创建: {uploader_folder_token}")
            uploader_folder_token = None
            # 删除失效的缓存
            from app.models.database import SessionLocal, FolderMapping
            session = SessionLocal()
            session.query(FolderMapping).filter_by(uploader_name=uploader_name, category="").delete()
            session.commit()
            session.close()

    # 如果 UP 主文件夹不存在，重新获取或创建
    if not uploader_folder_token:
        uploader_folder_token = _create_or_get_folder(
            Config.FEISHU_DOCS_FOLDER_TOKEN if Config.FEISHU_DOCS_FOLDER_TOKEN else None,
            uploader_name,
            token
        )
        if uploader_folder_token:
            _save_folder_mapping(uploader_name, "", uploader_folder_token, uploader_name)
            logger.info(f"重新创建 UP 主文件夹: {uploader_name} -> {uploader_folder_token}")

    # 4. 获取或创建分类文件夹
    if uploader_folder_token:
        # 先尝试在数据库中查找分类文件夹
        cached_category_token = _get_folder_mapping(uploader_name, category)
        if cached_category_token:
            # 验证缓存的分类文件夹是否仍然有效
            if _verify_folder_exists(cached_category_token, token):
                logger.debug(f"使用缓存的分类文件夹 token: {cached_category_token}")
                return cached_category_token
            else:
                logger.warning(f"缓存的分类文件夹已失效，重新创建: {cached_category_token}")
                # 删除失效的缓存
                from app.models.database import SessionLocal, FolderMapping
                session = SessionLocal()
                session.query(FolderMapping).filter_by(uploader_name=uploader_name, category=category).delete()
                session.commit()
                session.close()

        # 创建新的分类文件夹
        folder_token = _create_or_get_folder(uploader_folder_token, category, token)
        if folder_token:
            folder_path = f"{uploader_name}/{category}"
            _save_folder_mapping(uploader_name, category, folder_token, folder_path)
            logger.info(f"创建分类文件夹: {folder_path} -> {folder_token}")
            return folder_token

    return uploader_folder_token


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
        folder_token: 文件夹 token（None 表示根目录）

    Returns:
        成功返回文件信息，失败返回 None
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

    if not uploader_name:
        uploader_name = "默认UP主"

    # 1. 分类匹配
    category = _classify_title(uploader_name, title)
    if not category:
        category = "默认"
        logger.debug(f"标题 '{title}' 无匹配规则，使用默认分类")

    # 2. 确保文件夹存在
    folder_token = _ensure_category_folder_exists(uploader_name, category)
    if not folder_token:
        logger.warning(f"无法获取文件夹 token，使用根目录上传")
        folder_token = Config.FEISHU_DOCS_FOLDER_TOKEN if Config.FEISHU_DOCS_FOLDER_TOKEN else None

    # 3. 构建完整标题
    now = datetime.now()
    date_prefix = now.strftime("%Y%m%d")
    full_title = f"{date_prefix}_{bvid}_{title[:50]}"

    # 4. 上传
    result = upload_markdown_to_feishu(full_title, markdown_content, folder_token)

    return result