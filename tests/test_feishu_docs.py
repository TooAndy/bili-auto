"""
测试 feishu_docs.py - 飞书文档模块
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules import feishu_docs
from config import Config


def test_simple_markdown_to_blocks_basic():
    """测试：基本 Markdown 转换"""
    markdown = "# 标题1\n\n普通段落\n\n## 标题2"
    blocks = feishu_docs._simple_markdown_to_blocks(markdown)

    assert len(blocks) == 3
    assert blocks[0]["block_type"] == 2  # heading1
    assert blocks[1]["block_type"] == 1  # text
    assert blocks[2]["block_type"] == 3  # heading2


def test_simple_markdown_to_blocks_list():
    """测试：列表转换"""
    markdown = "- 列表项1\n- 列表项2"
    blocks = feishu_docs._simple_markdown_to_blocks(markdown)

    assert len(blocks) == 2
    assert blocks[0]["block_type"] == 7  # bullet
    assert blocks[1]["block_type"] == 7  # bullet


def test_simple_markdown_to_blocks_divider():
    """测试：分隔线转换"""
    markdown = "---"
    blocks = feishu_docs._simple_markdown_to_blocks(markdown)

    assert len(blocks) == 1
    assert blocks[0]["block_type"] == 19  # divider


def test_simple_markdown_to_blocks_bold():
    """测试：粗体转换"""
    markdown = "**粗体文字**"
    blocks = feishu_docs._simple_markdown_to_blocks(markdown)

    assert len(blocks) == 1
    assert blocks[0]["block_type"] == 1  # text
    assert blocks[0]["text"]["style"]["bold"] is True


def test_create_doc_from_markdown_disabled():
    """测试：功能未启用时返回 None"""
    with patch('config.Config') as mock_cfg:
        mock_cfg.FEISHU_DOCS_ENABLED = False
        original_config = feishu_docs.Config
        feishu_docs.Config = mock_cfg
        try:
            result = feishu_docs.push_video_summary_to_doc(
                "标题", "内容", "BV123", "UP主"
            )
            assert result is None
        finally:
            feishu_docs.Config = original_config


def test_create_doc_from_markdown_success():
    """测试：创建文档成功"""
    with patch('app.modules.push.get_feishu_tenant_access_token', return_value="test_token"):
        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "code": 0,
                "data": {
                    "document": {
                        "document_id": "doc123",
                        "title": "测试文档"
                    }
                }
            }
            mock_post.return_value = mock_response

            result = feishu_docs.create_doc_from_markdown(
                "测试标题", "# 标题\n内容", "folder123"
            )

            assert result is not None
            assert result["doc_token"] == "doc123"
            assert "https://bytedance.feishu.cn/docx/doc123" in result["url"]


def test_create_doc_from_markdown_failure():
    """测试：创建文档失败"""
    with patch('app.modules.push.get_feishu_tenant_access_token', return_value="test_token"):
        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "code": 10001,
                "msg": "invalid request"
            }
            mock_post.return_value = mock_response

            result = feishu_docs.create_doc_from_markdown(
                "测试标题", "内容"
            )

            assert result is None


def test_create_doc_from_markdown_no_token():
    """测试：没有 token 时返回 None"""
    with patch('app.modules.push.get_feishu_tenant_access_token', return_value=None):
        result = feishu_docs.create_doc_from_markdown("标题", "内容")
        assert result is None


def test_create_doc_simple_success():
    """测试：简单创建文档成功"""
    with patch('app.modules.push.get_feishu_tenant_access_token', return_value="test_token"):
        with patch('requests.post') as mock_post:
            # 第一次调用：创建文档
            mock_create_resp = MagicMock()
            mock_create_resp.json.return_value = {
                "code": 0,
                "data": {
                    "document": {
                        "document_id": "doc456",
                        "title": "测试简单文档"
                    }
                }
            }
            # 第二次调用：获取内容（可选）
            mock_get_resp = MagicMock()
            mock_get_resp.status_code = 200
            mock_get_resp.json.return_value = {"code": 0}

            mock_post.side_effect = [mock_create_resp, mock_get_resp]

            result = feishu_docs.create_doc_simple(
                "测试标题", "简单内容", "folder_token"
            )

            assert result is not None
            assert result["doc_token"] == "doc456"


def test_create_doc_simple_no_token():
    """测试：简单创建没有 token 时返回 None"""
    with patch('app.modules.push.get_feishu_tenant_access_token', return_value=None):
        result = feishu_docs.create_doc_simple("标题", "内容")
        assert result is None


def test_push_video_summary_to_doc_enabled():
    """测试：启用时尝试创建文档"""
    with patch('config.Config') as mock_cfg:
        mock_cfg.FEISHU_DOCS_ENABLED = True
        mock_cfg.FEISHU_DOCS_FOLDER_TOKEN = "folder_token"
        original_config = feishu_docs.Config
        feishu_docs.Config = mock_cfg

        try:
            with patch('app.modules.feishu_docs.create_doc_simple') as mock_simple:
                mock_simple.return_value = {
                    "doc_token": "doc789",
                    "url": "https://bytedance.feishu.cn/docx/doc789",
                    "title": "20260401_BV123_测试标题"
                }
                with patch('app.modules.feishu_docs.create_doc_from_markdown'):
                    result = feishu_docs.push_video_summary_to_doc(
                        "测试标题", "# 标题\n内容", "BV123", "UP主"
                    )

                    assert result is not None
                    assert result["doc_token"] == "doc789"
                    mock_simple.assert_called_once()
        finally:
            feishu_docs.Config = original_config


def test_push_video_summary_to_doc_fallback():
    """测试：简单方式失败时回退到 Markdown 方式"""
    with patch('config.Config') as mock_cfg:
        mock_cfg.FEISHU_DOCS_ENABLED = True
        mock_cfg.FEISHU_DOCS_FOLDER_TOKEN = "folder_token"
        original_config = feishu_docs.Config
        feishu_docs.Config = mock_cfg

        try:
            with patch('app.modules.feishu_docs.create_doc_simple', return_value=None):
                with patch('app.modules.feishu_docs.create_doc_from_markdown') as mock_md:
                    mock_md.return_value = {
                        "doc_token": "doc_fallback",
                        "url": "https://bytedance.feishu.cn/docx/doc_fallback",
                        "title": "测试"
                    }
                    result = feishu_docs.push_video_summary_to_doc(
                        "标题", "内容", "BV123", "UP主"
                    )

                    assert result is not None
                    assert result["doc_token"] == "doc_fallback"
                    mock_md.assert_called_once()
        finally:
            feishu_docs.Config = original_config
