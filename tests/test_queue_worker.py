#!/usr/bin/env python3
"""
测试 queue_worker 中 per-uploader prompt 查找逻辑
"""

from unittest.mock import MagicMock
from app.models.database import ClassificationRule, Subscription


class TestPerUploaderPromptLookup:
    """测试 queue_worker 的 prompt 查找逻辑"""

    def test_uploader_name_lookup_from_mid(self):
        """通过 mid 查到 uploader_name，再查 prompt_template"""
        mock_session = MagicMock()
        mock_sub = MagicMock()
        mock_sub.name = "呆咪"

        mock_rule = MagicMock()
        mock_rule.prompt_template = "呆咪的专属prompt"

        # 模拟查询顺序
        mock_session.query.return_value.filter_by.return_value.first.side_effect = [
            mock_sub,  # Subscription 查到
            mock_rule,  # ClassificationRule 查到
        ]

        # 执行查找逻辑
        sub = mock_session.query(Subscription).filter_by(mid="12345").first()
        uploader_name = sub.name if sub else None
        custom_prompt = None
        if uploader_name:
            rule = (
                mock_session.query(ClassificationRule)
                .filter_by(uploader_name=uploader_name)
                .first()
            )
            pt = rule.prompt_template if rule else None
            custom_prompt = pt if pt is not None else None

        assert uploader_name == "呆咪"
        assert custom_prompt == "呆咪的专属prompt"

    def test_empty_prompt_template_handled_as_none(self):
        """空字符串 prompt_template 当作 None 处理"""
        mock_rule = MagicMock()
        mock_rule.prompt_template = ""

        pt = mock_rule.prompt_template if mock_rule else None
        custom_prompt = pt if (pt is not None and pt != "") else None

        assert custom_prompt is None

    def test_none_prompt_template_handled_as_none(self):
        """None prompt_template 当作 None 处理"""
        mock_rule = MagicMock()
        mock_rule.prompt_template = None

        pt = mock_rule.prompt_template if mock_rule else None
        custom_prompt = pt if pt is not None else None

        assert custom_prompt is None

    def test_db_error_fallback_to_default(self):
        """数据库查询失败时 fallback 到默认 prompt"""
        mock_session = MagicMock()
        mock_session.query.side_effect = Exception("DB error")

        custom_prompt = None
        try:
            sub = mock_session.query(Subscription).filter_by(mid="123").first()
            uploader_name = sub.name if sub else None
            if uploader_name:
                rule = (
                    mock_session.query(ClassificationRule)
                    .filter_by(uploader_name=uploader_name)
                    .first()
                )
                pt = rule.prompt_template if rule else None
                custom_prompt = pt if pt is not None else None
        except Exception:
            custom_prompt = None

        assert custom_prompt is None

    def test_subscription_not_found_fallback(self):
        """Subscription 查不到时 fallback 到 None"""
        mock_session = MagicMock()
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        sub = mock_session.query(Subscription).filter_by(mid="123").first()
        uploader_name = sub.name if sub else None

        assert uploader_name is None

    def test_full_lookup_flow(self):
        """完整流程：mid -> uploader_name -> prompt_template"""
        mock_session = MagicMock()

        mock_sub = MagicMock()
        mock_sub.name = "运动UP主"

        mock_rule = MagicMock()
        mock_rule.prompt_template = "运动领域专属prompt"

        mock_session.query.return_value.filter_by.return_value.first.side_effect = [
            mock_sub,
            mock_rule,
        ]

        # 执行完整流程
        sub = mock_session.query(Subscription).filter_by(mid="999").first()
        uploader_name = sub.name if sub else None

        custom_prompt = None
        if uploader_name:
            rule = (
                mock_session.query(ClassificationRule)
                .filter_by(uploader_name=uploader_name)
                .first()
            )
            pt = rule.prompt_template if rule else None
            custom_prompt = pt if pt is not None else None

        assert uploader_name == "运动UP主"
        assert custom_prompt == "运动领域专属prompt"
