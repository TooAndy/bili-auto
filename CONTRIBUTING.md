# 开发流程

## 分支管理

- `main` 分支：只接收 squash merge，不直接 push
- 功能/修复开发使用 feature 分支，通过 PR 合并

## Commit Message 格式

使用 [Conventional Commits](https://www.conventionalcommits.org/)：

```
<type>: <描述>

feat:     新功能
fix:      修 bug
chore:    构建/工具/辅助功能
docs:     文档更新
refactor: 重构（不改变功能）
perf:     性能优化
test:     测试相关
```

Examples:
```
feat: add docker deployment support
fix: correct is_active boolean comparison in SQLAlchemy
chore: bump version to v1.0.0
docs: update README with Docker section
```

## 发布流程

1. 提交 PR 到 main，描述改动
2. CI 通过后，squash merge 到 main
3. release-please 自动检测 commit，生成/更新 CHANGELOG_PR_branch
4. 合并 CHANGELOG_PR_branch 后，release-please 自动打 tag
5. tag 触发 Docker 构建并推送到 GHCR

## 版本规则

遵循 Semantic Versioning (semver)：
- **major**: 不兼容的 API 变更
- **minor**: 向后兼容的新功能
- **patch**: 向后兼容的修 bug

## 获取镜像

```bash
# 最新版本
docker pull ghcr.io/tooandy/bili-auto:latest

# 指定版本
docker pull ghcr.io/tooandy/bili-auto:v1.0.0
```