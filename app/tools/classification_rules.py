#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书文档分类规则管理工具

Usage:
    bili-rules add --uploader 呆咪 --pattern "经济分析" --folder "每周经济分析"
    bili-rules list --uploader 呆咪
    bili-rules delete --id 1
    bili-rules test "第1150日投资记录" --uploader 呆咪
"""

import re
import sys
from pathlib import Path

import typer

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models.database import SessionLocal, ClassificationRule

app = typer.Typer(
    name="bili-rules",
    help="管理飞书文档分类规则",
    add_completion=False
)


@app.command()
def add(
    uploader: str = typer.Option(..., "--uploader", "-u", help="UP主名称，* 表示所有UP主"),
    pattern: str = typer.Option(..., "--pattern", "-p", help="正则表达式模式"),
    folder: str = typer.Option(..., "--folder", "-f", help="目标文件夹名称"),
    priority: int = typer.Option(100, "--priority", "-o", help="优先级，数字越小越先匹配"),
):
    """
    添加分类规则
    """
    # 验证正则表达式
    try:
        re.compile(pattern)
    except re.error as e:
        typer.secho(f"正则表达式错误: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)

    session = SessionLocal()
    try:
        rule = ClassificationRule(
            uploader_name=uploader,
            pattern=pattern,
            target_folder=folder,
            priority=priority
        )
        session.add(rule)
        session.commit()

        typer.secho(f"✓ 规则添加成功 (ID: {rule.id})", fg=typer.colors.GREEN)
        typer.secho(f"  UP主: {uploader}", fg=typer.colors.CYAN)
        typer.secho(f"  模式: {pattern}", fg=typer.colors.CYAN)
        typer.secho(f"  文件夹: {folder}", fg=typer.colors.CYAN)
        typer.secho(f"  优先级: {priority}", fg=typer.colors.CYAN)
    except Exception as e:
        session.rollback()
        typer.secho(f"添加规则失败: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)
    finally:
        session.close()


@app.command()
def list(
    uploader: str = typer.Option(None, "--uploader", "-u", help="筛选 UP 主，不指定则显示所有"),
    show_inactive: bool = typer.Option(False, "--show-inactive", help="显示已禁用的规则"),
):
    """
    列出分类规则
    """
    session = SessionLocal()
    try:
        query = session.query(ClassificationRule)

        if uploader:
            query = query.filter(
                (ClassificationRule.uploader_name == uploader) |
                (ClassificationRule.uploader_name == "*")
            )

        if not show_inactive:
            query = query.filter(ClassificationRule.is_active == True)

        rules = query.order_by(ClassificationRule.uploader_name, ClassificationRule.priority).all()

        if not rules:
            typer.secho("没有找到规则", fg=typer.colors.YELLOW)
            return

        # 标题
        typer.secho("\n{:<4} {:<15} {:<30} {:<15} {:<8} {:<8}".format(
            "ID", "UP主", "模式", "文件夹", "优先级", "状态"
        ), fg=typer.colors.CYAN, bold=True)
        typer.secho("-" * 90)

        for rule in rules:
            status = "✓" if rule.is_active else "✗"
            fg = typer.colors.GREEN if rule.is_active else typer.colors.YELLOW
            typer.secho("{:<4} {:<15} {:<30} {:<15} {:<8} {:<8}".format(
                rule.id,
                rule.uploader_name[:13],
                rule.pattern[:28],
                rule.target_folder[:13],
                rule.priority,
                status
            ), fg=fg)

        typer.secho(f"\n共 {len(rules)} 条规则\n", fg=typer.colors.CYAN)
    finally:
        session.close()


@app.command()
def delete(
    rule_id: int = typer.Argument(..., help="规则 ID"),
    force: bool = typer.Option(False, "--force", "-y", help="跳过确认"),
):
    """
    删除规则
    """
    session = SessionLocal()
    try:
        rule = session.query(ClassificationRule).filter_by(id=rule_id).first()

        if not rule:
            typer.secho(f"规则不存在: ID {rule_id}", fg=typer.colors.RED)
            raise typer.Exit(1)

        if not force:
            confirm = typer.confirm(
                f"确认删除规则?\n"
                f"  UP主: {rule.uploader_name}\n"
                f"  模式: {rule.pattern}\n"
                f"  文件夹: {rule.target_folder}"
            )
            if not confirm:
                typer.secho("取消删除", fg=typer.colors.YELLOW)
                return

        session.delete(rule)
        session.commit()
        typer.secho(f"✓ 规则已删除 (ID: {rule_id})", fg=typer.colors.GREEN)
    except Exception as e:
        session.rollback()
        typer.secho(f"删除规则失败: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)
    finally:
        session.close()


@app.command()
def disable(
    rule_id: int = typer.Argument(..., help="规则 ID"),
):
    """
    禁用规则
    """
    session = SessionLocal()
    try:
        rule = session.query(ClassificationRule).filter_by(id=rule_id).first()

        if not rule:
            typer.secho(f"规则不存在: ID {rule_id}", fg=typer.colors.RED)
            raise typer.Exit(1)

        rule.is_active = False
        session.commit()
        typer.secho(f"✓ 规则已禁用 (ID: {rule_id})", fg=typer.colors.GREEN)
    except Exception as e:
        session.rollback()
        typer.secho(f"禁用规则失败: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)
    finally:
        session.close()


@app.command()
def enable(
    rule_id: int = typer.Argument(..., help="规则 ID"),
):
    """
    启用规则
    """
    session = SessionLocal()
    try:
        rule = session.query(ClassificationRule).filter_by(id=rule_id).first()

        if not rule:
            typer.secho(f"规则不存在: ID {rule_id}", fg=typer.colors.RED)
            raise typer.Exit(1)

        rule.is_active = True
        session.commit()
        typer.secho(f"✓ 规则已启用 (ID: {rule_id})", fg=typer.colors.GREEN)
    except Exception as e:
        session.rollback()
        typer.secho(f"启用规则失败: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)
    finally:
        session.close()


@app.command()
def test(
    title: str = typer.Argument(..., help="视频标题"),
    uploader: str = typer.Option(..., "--uploader", "-u", help="UP主名称"),
):
    """
    测试标题会匹配到哪个规则
    """
    from app.modules.feishu_docs import _classify_title

    category = _classify_title(uploader, title)

    if category:
        typer.secho(f"✓ 匹配结果: {category}", fg=typer.colors.GREEN, bold=True)
    else:
        typer.secho("✗ 无匹配规则，将使用默认分类", fg=typer.colors.YELLOW, bold=True)


if __name__ == "__main__":
    app()