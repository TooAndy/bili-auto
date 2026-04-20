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

class TestSaveFolderMapping:
    """测试 _save_folder_mapping"""

    def test_save_new_mapping(self):
        """测试：保存新映射"""
        with patch('app.models.database.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            mock_db.query.return_value.filter_by.return_value.first.return_value = None

            feishu_docs._save_folder_mapping("呆咪", "投资", "token_abc", "呆咪/投资")
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()

    def test_save_update_existing_mapping(self):
        """测试：更新已有映射"""
        with patch('app.models.database.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            existing = MagicMock()
            mock_db.query.return_value.filter_by.return_value.first.return_value = existing

            feishu_docs._save_folder_mapping("呆咪", "投资", "new_token", "呆咪/投资")
            assert existing.folder_token == "new_token"
            mock_db.commit.assert_called()

    def test_save_rollback_on_error(self):
        """测试：异常时回滚"""
        with patch('app.models.database.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            mock_db.commit.side_effect = Exception("db error")
            mock_db.query.return_value.filter_by.return_value.first.return_value = None

            feishu_docs._save_folder_mapping("呆咪", "投资", "token", "呆咪/投资")
            mock_db.rollback.assert_called()


class TestVerifyFolderExists:
    """测试 _verify_folder_exists"""

    def test_folder_exists(self):
        """测试：文件夹存在"""
        with patch('app.modules.feishu_docs.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"code": 0}
            mock_get.return_value = mock_response

            result = feishu_docs._verify_folder_exists("folder_token_123", "test_token")
            assert result is True

    def test_folder_not_exists(self):
        """测试：文件夹不存在"""
        with patch('app.modules.feishu_docs.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"code": 99999}
            mock_get.return_value = mock_response

            result = feishu_docs._verify_folder_exists("invalid_token", "test_token")
            assert result is False

    def test_verify_request_exception(self):
        """测试：请求异常返回 False"""
        with patch('app.modules.feishu_docs.requests.get') as mock_get:
            mock_get.side_effect = Exception("network error")

            result = feishu_docs._verify_folder_exists("folder_token", "test_token")
            assert result is False


class TestFindFolderInFeishu:
    """测试 _find_folder_in_feishu"""

    def test_no_parent_token(self):
        """测试：无父目录时返回 None"""
        result = feishu_docs._find_folder_in_feishu(None, "测试文件夹", "fake_token")
        assert result is None

    def test_folder_found(self):
        """测试：找到同名文件夹"""
        with patch('app.modules.feishu_docs.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "code": 0,
                "data": {
                    "files": [
                        {"type": "file", "name": "a.txt", "token": "token_a"},
                        {"type": "folder", "name": "测试文件夹", "token": "found_token"},
                    ]
                }
            }
            mock_get.return_value = mock_response

            result = feishu_docs._find_folder_in_feishu("parent_123", "测试文件夹", "fake_token")
            assert result == "found_token"

    def test_folder_not_found(self):
        """测试：未找到文件夹"""
        with patch('app.modules.feishu_docs.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"code": 0, "data": {"files": []}}
            mock_get.return_value = mock_response

            result = feishu_docs._find_folder_in_feishu("parent_123", "不存在", "fake_token")
            assert result is None

    def test_find_folder_request_exception(self):
        """测试：请求异常返回 None"""
        with patch('app.modules.feishu_docs.requests.get') as mock_get:
            mock_get.side_effect = Exception("error")

            result = feishu_docs._find_folder_in_feishu("parent", "文件夹", "fake_token")
            assert result is None


class TestCreateOrGetFolder:
    """测试 _create_or_get_folder"""

    def test_folder_already_exists(self):
        """测试：文件夹已存在"""
        with patch('app.modules.feishu_docs._find_folder_in_feishu', return_value="existing_token"):
            result = feishu_docs._create_or_get_folder("parent", "已存在", "fake_token")
            assert result == "existing_token"

    def test_create_folder_success(self):
        """测试：创建文件夹成功"""
        with patch('app.modules.feishu_docs._find_folder_in_feishu', return_value=None):
            with patch('requests.post') as mock_post:
                mock_response = MagicMock()
                mock_response.json.return_value = {
                    "code": 0,
                    "data": {"token": "new_token_xyz"}
                }
                mock_post.return_value = mock_response

                result = feishu_docs._create_or_get_folder("parent", "新文件夹", "fake_token")
                assert result == "new_token_xyz"

    def test_create_folder_failure(self):
        """测试：创建文件夹失败"""
        with patch('app.modules.feishu_docs._find_folder_in_feishu', return_value=None):
            with patch('requests.post') as mock_post:
                mock_response = MagicMock()
                mock_response.json.return_value = {"code": 99999, "msg": "failed"}
                mock_post.return_value = mock_response

                result = feishu_docs._create_or_get_folder("parent", "新文件夹", "fake_token")
                assert result is None

    def test_create_folder_exception(self):
        """测试：创建文件夹请求异常"""
        with patch('app.modules.feishu_docs._find_folder_in_feishu', return_value=None):
            with patch('requests.post') as mock_post:
                mock_post.side_effect = Exception("network error")

                result = feishu_docs._create_or_get_folder("parent", "新文件夹", "fake_token")
                assert result is None


class TestClassifyTitleEdge:
    """测试 _classify_title 边界情况"""

    def test_regex_error_handled(self):
        """测试：正则表达式错误被捕获"""
        with patch('app.models.database.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            # 创建一个会触发 re.error 的规则
            mock_rule = MagicMock()
            mock_rule.pattern = "[invalid"  # 无效正则
            mock_rule.target_folder = "目标"
            mock_rule.is_active = True

            mock_query = MagicMock()
            mock_query.filter.return_value.order_by.return_value.all.return_value = [mock_rule]
            mock_db.query.return_value = mock_query

            # 应该返回 None 而不是崩溃
            result = feishu_docs._classify_title("呆咪", "测试标题")
            assert result is None


class TestUploadMarkdownEdge:
    """测试 upload_markdown_to_feishu 边界情况"""

    def test_token_none(self):
        """测试：token 获取失败"""
        with patch('app.modules.push.get_feishu_tenant_access_token', return_value=None):
            result = feishu_docs.upload_markdown_to_feishu(
                title="测试",
                markdown_content="# test"
            )
            assert result is None

    def test_upload_request_exception(self):
        """测试：上传请求异常"""
        with patch('app.modules.push.get_feishu_tenant_access_token', return_value="fake_token"):
            with patch('requests.post') as mock_post:
                mock_post.side_effect = Exception("connection error")

                result = feishu_docs.upload_markdown_to_feishu(
                    title="测试",
                    markdown_content="# test",
                    folder_token="folder123"
                )
                assert result is None
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
