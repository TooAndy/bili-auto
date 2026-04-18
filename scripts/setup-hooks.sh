#!/bin/bash
# setup-hooks.sh - 安装 git hooks

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

echo "Installing git hooks..."

# 创建 hooks 目录（如果不存在）
mkdir -p "$REPO_DIR/.git/hooks"

# 复制 pre-push hook
if [ -f "$SCRIPT_DIR/pre-push.sh" ]; then
    cp "$SCRIPT_DIR/pre-push.sh" "$REPO_DIR/.git/hooks/pre-push"
    chmod +x "$REPO_DIR/.git/hooks/pre-push"
    echo "Installed pre-push hook"
fi

echo "Done!"
