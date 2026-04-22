#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书文档分类规则管理工具

Usage:
    # LLM 智能分类（推荐）
    bili-rules add-folder --uploader 呆咪 --folder "每日投资记录"
    bili-rules add-folder --uploader 呆咪 --folder "闲聊"
    bili-rules list-folders --uploader 呆咪
    bili-rules remove-folder --uploader 呆咪 --folder "闲聊"

    # 正则表达式规则
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


@app.command("list")
def list_rules(
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
            query = query.filter(ClassificationRule.is_active is True)

        rules = query.order_by(ClassificationRule.uploader_name, ClassificationRule.priority).all()

        if not rules:
            typer.secho("没有找到规则", fg=typer.colors.YELLOW)
            return

        # 标题
        typer.secho("\n{:<4} {:<15} {:<30} {:<22} {:<8} {:<8}".format(
            "ID", "UP主", "模式", "文件夹", "优先级", "状态"
        ), fg=typer.colors.CYAN, bold=True)
        typer.secho("-" * 95)

        for rule in rules:
            status = "✓" if rule.is_active else "✗"
            fg = typer.colors.GREEN if rule.is_active else typer.colors.YELLOW
            # 处理 pattern 和 target_folder 为 None 的情况（LLM 配置）
            if rule.pattern is None and rule.llm_folders:
                pattern_str = "LLM"
                folder_str = ", ".join(rule.llm_folders)[:20]
            else:
                pattern_str = (rule.pattern or "")[:28]
                folder_str = (rule.target_folder or "")[:20]
            typer.secho("{:<4} {:<15} {:<30} {:<22} {:<8} {:<8}".format(
                rule.id,
                rule.uploader_name[:13],
                pattern_str,
                folder_str,
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
def add_folder(
    uploader: str = typer.Option(..., "--uploader", "-u", help="UP主名称"),
    folder: str = typer.Option(..., "--folder", "-f", help="文件夹名称"),
):
    """
    添加 LLM 分类文件夹配置

    Example:
        bili-rules add-folder --uploader 呆咪 --folder "每日投资记录"
    """
    session = SessionLocal()
    try:
        # 查找该 UP 主是否已有 LLM 配置
        config = session.query(ClassificationRule).filter(
            ClassificationRule.uploader_name == uploader,
            ClassificationRule.llm_folders.isnot(None)
        ).first()

        if config:
            # 追加到现有列表
            folders = list(config.llm_folders)  # 创建副本以触发 SQLAlchemy 变化检测
            if folder in folders:
                typer.secho(f"文件夹 '{folder}' 已存在", fg=typer.colors.YELLOW)
                return
            folders.append(folder)
            config.llm_folders = folders
            typer.secho(f"✓ 已添加文件夹到配置 (ID: {config.id})", fg=typer.colors.GREEN)
        else:
            # 创建新配置
            config = ClassificationRule(
                uploader_name=uploader,
                llm_folders=[folder]
            )
            session.add(config)
            typer.secho(f"✓ LLM 文件夹配置已创建 (ID: {config.id})", fg=typer.colors.GREEN)

        session.commit()
        typer.secho(f"  UP主: {uploader}", fg=typer.colors.CYAN)
        typer.secho(f"  文件夹: {folder}", fg=typer.colors.CYAN)
    except Exception as e:
        session.rollback()
        typer.secho(f"添加文件夹失败: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)
    finally:
        session.close()


@app.command()
def list_folders(
    uploader: str = typer.Option(None, "--uploader", "-u", help="筛选 UP 主，不指定则显示所有"),
):
    """
    列出已配置的 LLM 分类文件夹

    Example:
        bili-rules list-folders
        bili-rules list-folders --uploader 呆咪
    """
    session = SessionLocal()
    try:
        query = session.query(ClassificationRule).filter(
            ClassificationRule.llm_folders.isnot(None)
        )

        if uploader:
            query = query.filter(ClassificationRule.uploader_name == uploader)

        configs = query.all()

        if not configs:
            typer.secho("没有找到 LLM 文件夹配置", fg=typer.colors.YELLOW)
            return

        typer.secho("\n{:<4} {:<15} {:<30}".format(
            "ID", "UP主", "文件夹"
        ), fg=typer.colors.CYAN, bold=True)
        typer.secho("-" * 60)

        for config in configs:
            folders_str = ", ".join(config.llm_folders)
            typer.secho("{:<4} {:<15} {:<30}".format(
                config.id,
                config.uploader_name[:13],
                folders_str[:28]
            ), fg=typer.colors.GREEN)

        typer.secho(f"\n共 {len(configs)} 条配置\n", fg=typer.colors.CYAN)
    finally:
        session.close()


@app.command()
def remove_folder(
    uploader: str = typer.Option(..., "--uploader", "-u", help="UP主名称"),
    folder: str = typer.Option(..., "--folder", "-f", help="文件夹名称"),
):
    """
    移除 LLM 分类文件夹配置

    Example:
        bili-rules remove-folder --uploader 呆咪 --folder "每日投资记录"
    """
    session = SessionLocal()
    try:
        config = session.query(ClassificationRule).filter(
            ClassificationRule.uploader_name == uploader,
            ClassificationRule.llm_folders.isnot(None)
        ).first()

        if not config:
            typer.secho(f"未找到 UP主 '{uploader}' 的 LLM 配置", fg=typer.colors.RED)
            raise typer.Exit(1)

        if folder not in config.llm_folders:
            typer.secho(f"文件夹 '{folder}' 不存在", fg=typer.colors.RED)
            raise typer.Exit(1)

        config.llm_folders.remove(folder)
        session.commit()

        typer.secho(f"✓ 已移除文件夹 '{folder}'", fg=typer.colors.GREEN)
        typer.secho(f"  剩余文件夹: {config.llm_folders}", fg=typer.colors.CYAN)
    except Exception as e:
        session.rollback()
        typer.secho(f"移除文件夹失败: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)
    finally:
        session.close()


@app.command()
def test(
    title: str = typer.Argument(..., help="视频标题"),
    uploader: str = typer.Option(..., "--uploader", "-u", help="UP主名称"),
):
    """
    测试标题会匹配到哪个分类

    Example:
        bili-rules test "第1150日投资记录" --uploader 呆咪
    """
    from app.modules.feishu_docs import _classify_title

    # 检查使用哪种分类方式
    session = SessionLocal()
    try:
        llm_config = session.query(ClassificationRule).filter(
            ClassificationRule.uploader_name == uploader,
            ClassificationRule.llm_folders.isnot(None)
        ).first()
        has_llm = bool(llm_config and llm_config.llm_folders)
    finally:
        session.close()

    method = "LLM" if has_llm else "正则"
    typer.secho(f"分类方式: {method}", fg=typer.colors.CYAN)

    category = _classify_title(uploader, title)

    if category:
        typer.secho(f"✓ 匹配结果: {category}", fg=typer.colors.GREEN, bold=True)
    else:
        typer.secho("✗ 无匹配规则，将使用默认分类", fg=typer.colors.YELLOW, bold=True)


if __name__ == "__main__":
    app()