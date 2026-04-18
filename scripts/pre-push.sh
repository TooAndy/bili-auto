#!/bin/bash
# pre-push.sh - 推送前检查脚本
# 使用方式: ./scripts/pre-push.sh
# 或安装为 git hook: cp scripts/pre-push.sh .git/hooks/pre-push

set -e

echo "=========================================="
echo "Pre-push Checks"
echo "=========================================="

# 检查是否在 git 仓库中
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "Error: Not in a git repository"
    exit 1
fi

# 检查是否有未提交的更改
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Warning: You have uncommitted changes"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo "Running pytest with coverage..."
echo ""

# 使用 uv 运行测试
if command -v uv &> /dev/null; then
    uv run pytest --cov=app --cov-fail-under=85 -q
else
    # fallback to python -m pytest
    python -m pytest --cov=app --cov-fail-under=85 -q
fi

echo ""
echo "=========================================="
echo "All checks passed! Ready to push."
echo "=========================================="
