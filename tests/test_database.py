#!/usr/bin/env python3
"""
测试 database.py 的迁移逻辑
"""

from unittest.mock import MagicMock
from app.models.database import _add_column_if_missing


class TestAddColumnIfMissing:
    """测试 _add_column_if_missing 抽象函数"""

    def test_add_column_when_missing(self):
        """列不存在时应该添加"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(0, "id"), (1, "name")]
        mock_session.execute.return_value = mock_result

        _add_column_if_missing(mock_session, "test_table", "new_column")

        # 验证 execute 被调用了 2 次（PRAGMA + ALTER）
        assert mock_session.execute.call_count == 2
        mock_session.commit.assert_called_once()

    def test_skip_when_column_exists(self):
        """列已存在时不应添加"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (0, "id"),
            (1, "name"),
            (2, "existing_column"),
        ]
        mock_session.execute.return_value = mock_result

        _add_column_if_missing(mock_session, "test_table", "existing_column")

        mock_session.commit.assert_not_called()

    def test_custom_column_type(self):
        """支持自定义列类型"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(0, "id")]
        mock_session.execute.return_value = mock_result

        _add_column_if_missing(mock_session, "test_table", "json_col", "JSON")

        for call in mock_session.execute.call_args_list:
            if "ALTER" in str(call):
                assert "JSON" in str(call)
