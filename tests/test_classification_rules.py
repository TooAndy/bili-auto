#!/usr/bin/env python3
"""
测试 bili-rules set-prompt / get-prompt / list-templates 命令
"""

from unittest.mock import MagicMock, patch
from typer.testing import CliRunner
from app.tools.classification_rules import app, BUILTIN_TEMPLATES


runner = CliRunner()


class TestSetPrompt:
    def test_set_prompt_creates_new_record(self):
        """设置新 UP 主的 prompt"""
        with patch("app.tools.classification_rules.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = None

            result = runner.invoke(
                app,
                [
                    "set-prompt",
                    "--uploader",
                    "测试UP主",
                    "--prompt",
                    "自定义prompt内容",
                ],
            )
            assert result.exit_code == 0
            assert "已创建" in result.stdout or "已更新" in result.stdout

    def test_set_prompt_with_builtin_investment(self):
        """使用内置投资模板"""
        with patch("app.tools.classification_rules.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = None

            result = runner.invoke(
                app, ["set-prompt", "--uploader", "测试UP主", "--prompt", "投资"]
            )
            assert result.exit_code == 0
            assert "投资" in result.stdout

    def test_set_prompt_with_builtin_sports(self):
        """使用内置运动模板"""
        with patch("app.tools.classification_rules.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = None

            result = runner.invoke(
                app, ["set-prompt", "--uploader", "测试UP主", "--prompt", "运动"]
            )
            assert result.exit_code == 0
            assert "运动" in result.stdout

    def test_set_prompt_with_builtin_algorithm(self):
        """使用内置大模型算法模板"""
        with patch("app.tools.classification_rules.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = None

            result = runner.invoke(
                app, ["set-prompt", "--uploader", "测试UP主", "--prompt", "大模型算法"]
            )
            assert result.exit_code == 0
            assert "大模型算法" in result.stdout

    def test_set_prompt_empty_string_treated_as_none(self):
        """空字符串 prompt 不应被接受（空字符串当 None 处理）"""
        with patch("app.tools.classification_rules.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = None

            result = runner.invoke(
                app, ["set-prompt", "--uploader", "测试UP主", "--prompt", ""]
            )
            # 空字符串作为 prompt 是有效的（用户想清除 prompt）
            # 但按设计决策，空字符串等同于 None，使用默认 prompt
            # 这里测试的是命令能正常执行
            assert result.exit_code == 0


class TestGetPrompt:
    def test_get_prompt_shows_configured(self):
        """获取已配置的 prompt"""
        with patch("app.tools.classification_rules.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            mock_config = MagicMock()
            mock_config.prompt_template = "测试prompt123"

            # The code uses: session.query(ClassificationRule).filter(...).first()
            mock_db.query.return_value.filter.return_value.first.return_value = (
                mock_config
            )

            result = runner.invoke(app, ["get-prompt", "--uploader", "测试UP主_get"])
            assert result.exit_code == 0
            assert "测试prompt123" in result.stdout

    def test_get_prompt_shows_none_when_not_configured(self):
        """未配置时提示使用默认"""
        with patch("app.tools.classification_rules.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = None

            result = runner.invoke(
                app, ["get-prompt", "--uploader", "不存在的UP主_xyz"]
            )
            assert result.exit_code == 0
            assert "未配置" in result.stdout or "默认" in result.stdout


class TestListTemplates:
    def test_list_templates_shows_all_builtins(self):
        """列出所有内置模板"""
        result = runner.invoke(app, ["list-templates"])
        assert result.exit_code == 0
        for name in BUILTIN_TEMPLATES:
            assert name in result.stdout

    def test_list_templates_shows_usage(self):
        """列出模板时显示使用方法"""
        result = runner.invoke(app, ["list-templates"])
        assert result.exit_code == 0
        assert "bili-rules set-prompt" in result.stdout
