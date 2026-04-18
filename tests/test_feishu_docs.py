"""
测试 feishu_docs.py - 飞书文档模块
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules import feishu_docs


class TestClassifyTitle:
    """测试标题分类"""

    def test_classify_with_matching_rule(self):
        """测试：标题匹配规则"""
        with patch('app.models.database.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            # Mock a classification rule
            mock_rule = MagicMock()
            mock_rule.pattern = "投资记录"
            mock_rule.target_folder = "每日投资记录"
            mock_rule.uploader_name = "呆咪"
            mock_rule.is_active = True

            mock_query = MagicMock()
            mock_query.filter.return_value.order_by.return_value.all.return_value = [mock_rule]
            mock_db.query.return_value = mock_query

            result = feishu_docs._classify_title("呆咪", "第1150日投资记录")
            assert result == "每日投资记录"

    def test_classify_no_match(self):
        """测试：无匹配规则返回 None"""
        with patch('app.models.database.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            mock_query = MagicMock()
            mock_query.filter.return_value.order_by.return_value.all.return_value = []
            mock_db.query.return_value = mock_query

            result = feishu_docs._classify_title("呆咪", "无关内容")
            assert result is None


class TestFolderMapping:
    """测试文件夹映射"""

    def test_get_folder_mapping_exists(self):
        """测试：获取已缓存的文件夹映射"""
        with patch('app.models.database.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            mock_mapping = MagicMock()
            mock_mapping.folder_token = "token123"

            mock_query = MagicMock()
            mock_query.filter_by.return_value.first.return_value = mock_mapping
            mock_db.query.return_value = mock_query

            result = feishu_docs._get_folder_mapping("呆咪", "每日投资记录")
            assert result == "token123"

    def test_get_folder_mapping_not_exists(self):
        """测试：文件夹映射不存在"""
        with patch('app.models.database.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            mock_query = MagicMock()
            mock_query.filter_by.return_value.first.return_value = None
            mock_db.query.return_value = mock_query

            result = feishu_docs._get_folder_mapping("呆咪", "默认")
            assert result is None


class TestPushVideoSummary:
    """测试视频摘要上传"""

    def test_push_disabled(self):
        """测试：功能未启用时返回 None"""
        with patch('config.Config') as mock_cfg:
            mock_cfg.FEISHU_DOCS_ENABLED = False
            original = feishu_docs.Config
            feishu_docs.Config = mock_cfg
            try:
                result = feishu_docs.push_video_summary_to_doc(
                    title="测试标题",
                    markdown_content="# 测试",
                    bvid="BV123",
                    uploader_name="呆咪"
                )
                assert result is None
            finally:
                feishu_docs.Config = original

    def test_push_with_pub_time(self):
        """测试：使用发布时间戳"""
        with patch('app.modules.push.get_feishu_tenant_access_token', return_value=None):
            with patch('config.Config') as mock_cfg:
                mock_cfg.FEISHU_DOCS_ENABLED = True
                mock_cfg.FEISHU_DOCS_FOLDER_TOKEN = None
                original = feishu_docs.Config
                feishu_docs.Config = mock_cfg
                try:
                    # 不会真正发送，因为 token 是 None
                    result = feishu_docs.push_video_summary_to_doc(
                        title="测试标题",
                        markdown_content="# 测试内容",
                        bvid="BV123",
                        pub_time=1712000000,  # 2024-04-01
                        uploader_name="呆咪"
                    )
                    # 返回 None 是因为 token 获取失败
                    assert result is None
                finally:
                    feishu_docs.Config = original


class TestUploadMarkdown:
    """测试 Markdown 上传"""

    def test_upload_success(self):
        """测试：上传成功"""
        with patch('app.modules.push.get_feishu_tenant_access_token', return_value="test_token"):
            with patch('requests.post') as mock_post:
                mock_response = MagicMock()
                mock_response.json.return_value = {
                    "code": 0,
                    "data": {
                        "file_token": "file123",
                        "url": "https://feishu.cn/file/file123"
                    }
                }
                mock_post.return_value = mock_response

                result = feishu_docs.upload_markdown_to_feishu(
                    title="测试文档",
                    markdown_content="# 测试内容",
                    folder_token="folder123"
                )

                assert result is not None
                assert result["file_token"] == "file123"
                assert "feishu.cn" in result["url"]

    def test_upload_failure(self):
        """测试：上传失败"""
        with patch('app.modules.push.get_feishu_tenant_access_token', return_value="test_token"):
            with patch('requests.post') as mock_post:
                mock_response = MagicMock()
                mock_response.json.return_value = {
                    "code": 99999,
                    "msg": "upload failed"
                }
                mock_post.return_value = mock_response

                result = feishu_docs.upload_markdown_to_feishu(
                    title="测试文档",
                    markdown_content="# 测试",
                    folder_token="folder123"
                )

                assert result is None
