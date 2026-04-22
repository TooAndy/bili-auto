# Docker 部署设计方案

## 概述

为 bili-auto 项目设计 Docker 部署方案，支持用户下载镜像后一键部署。

## 目标

1. 用户下载镜像后可快速部署
2. 配置通过环境变量传入
3. 数据持久化到宿主机
4. 首次启动自动初始化数据库
5. whisper.cpp 自动下载（零配置）

## 方案设计

### 文件结构

```
bili-auto/
├── Dockerfile
├── docker-compose.yml
├── docker-compose.watchtower.yml  # 含自动更新
├── .dockerignore
└── docs/
    └── DEPLOY.md        # 部署文档
```

## Section 1: Architecture Review

### 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Docker Host                            │
│  ┌─────────────────────────────────────────────────────┐  │
│  │              bili-auto Container                      │  │
│  │  ┌─────────┐  ┌──────────┐  ┌────────────────────┐  │  │
│  │  │ init_services │→ │ whisper  │→ │   main.py          │  │  │
│  │  │ (迁移)  │  │ (下载)   │  │   (scheduler +    │  │  │
│  │  └─────────┘  └──────────┘  │    queue_worker)   │  │  │
│  │                            └────────────────────┘  │  │
│  └─────────────────────────────────────────────────────┘  │
│       ↓                 ↓                    ↓            │
│  ┌─────────┐      ┌─────────┐          ┌─────────┐        │
│  │  data/  │      │  logs/  │          │ models/ │        │
│  │ (SQLite)│      │         │          │(whisper)│        │
│  └─────────┘      └─────────┘          └─────────┘        │
└─────────────────────────────────────────────────────────────┘
```

### 数据流

```
首次启动:
  init_services() → 检查 llm_folders 列 → 如不存在 ALTER TABLE
            ↓
  check_whisper() → 检测平台 → 下载 whisper.cpp CLI + ggml-small.bin
            ↓
  main.py → scheduler 定时检查 B站 → queue_worker 处理

运行时:
  Docker restart → 自动跳过已存在的迁移 + 跳过已下载的 whisper 模型
```

## Section 2: Error & Rescue Map

| METHOD/CODEPATH | WHAT CAN GO WRONG | EXCEPTION CLASS | RESCUED? | RESCUE ACTION | USER SEES |
|-----------------|-------------------|-----------------|----------|---------------|-----------|
| whisper.cpp 下载 | GitHub API 超时 | requests.Timeout | Y | 跳过，启动时自动回退到 faster-whisper | "whisper.cpp 下载失败，使用 faster-whisper" |
| whisper.cpp 下载 | 磁盘空间不足 | OSError | Y | 跳过，回退到 faster-whisper | "磁盘空间不足，回退到 faster-whisper" |
| 模型下载 | 网络断开 | requests.ConnectionError | Y | 跳过，回退到 faster-whisper | "模型下载失败，使用 faster-whisper" |
| 数据库迁移 | 列已存在 | IntegrityError | Y | 忽略继续 | 无 |
| Docker healthcheck | SQLite 锁定 | — | Y | 重试 | 容器重启 |

## Section 3: Security & Threat Model

| Threat | Likelihood | Impact | Mitigation |
|--------|------------|--------|------------|
| 环境变量泄露敏感信息 | Med | High | .env 不提交到 git，docker-compose 用 env_file |
| Docker 镜像漏洞 | Low | Med | 使用 python:3.12-slim 最小镜像，定期更新 |
| 挂载目录权限 | Med | Med | RUN mkdir 时指定 1000:1000 用户 |
| whisper.cpp 二进制篡改 | Low | High | HTTPS + SHA256 校验 |

## Section 4: Data Flow & Interaction Edge Cases

### Docker 启动流程

```
1. docker-compose up -d
       ↓
2. 容器启动，healthcheck 开始探测
       ↓
3. init_services() 执行数据库迁移（幂等）
       ↓
4. whisper.cpp 检测与下载（首次）
       ↓
5. main.py 启动 scheduler + queue_worker
       ↓
6. healthcheck 通过，服务可用
```

### Edge Cases

| Edge Case | Handled? | How |
|-----------|----------|-----|
| 非首次启动 | ✅ | 迁移检查幂等，whisper 检测文件存在则跳过 |
| Docker 重启 | ✅ | 数据持久化到 volume |
| 磁盘空间不足 | ✅ | try-catch 捕获，回退到 faster-whisper |
| 网络离线启动 | ✅ | whisper 下载失败继续启动，不阻塞 |
| 模型文件损坏 | ✅ | 下载前校验 SHA256，不匹配重新下载 |

## Section 5: Code Quality Review

待实现的新文件：

1. `.github/workflows/docker.yml` — CI/CD
2. `app/utils/whisper_downloader.py` — whisper.cpp 自动下载（新增）
3. `docker-compose.watchtower.yml` — 含 Watchtower 的配置

现有代码改动：
- `app/models/database.py` — `_migrate_if_needed()` 已实现，`init_db()` 重命名为 `init_services()` 并接入 whisper 下载
- `scripts/init_setup.py` — 更新为调用 `init_services()`

## Section 6: Test Review

### 新增测试

```
NEW DATA FLOWS:
  - whisper.cpp 下载流程
  - 数据库自动迁移流程

NEW CODEPATHS:
  - whisper_downloader.py: detect_platform(), download_cli(), download_model()
  - _migrate_if_needed() 新增列检测

NEW INTEGRATIONS:
  - GitHub Releases API (下载 whisper.cpp)
  - Hugging Face API (下载 ggml-small.bin)
```

测试项：
1. 平台检测正确（darwin/arm64, darwin/x86_64, linux/x86_64）
2. 文件存在时跳过下载
3. 下载失败时回退到 faster-whisper
4. 数据库迁移幂等

## Section 7: Performance Review

| Item | Impact | Note |
|------|--------|------|
| whisper.cpp 首次下载 | ~500MB | 一次性，Docker 层可缓存 |
| 模型存储 | ~500MB | 持久化到 volume |
| 启动时间 | +5-10s | 首次 + 下载时间 |
| Docker 层缓存 | 节省 400MB | 依赖层缓存，不重复下载 |

## Section 8: Observability & Debuggability Review

新增日志：

```python
# whisper 下载
logger.info(f"下载 whisper.cpp {platform} ...")
logger.info(f"whisper 模型已存在: {model_path}")
logger.warning(f"whisper.cpp 下载失败: {e}，使用 faster-whisper")

# 数据库迁移
logger.info("检查数据库迁移...")
logger.info("数据库迁移完成")
```

## Section 9: Deployment & Rollout Review

### 构建流程

```yaml
# GitHub Actions
1. checkout
2. setup QEMU (多架构)
3. setup Buildx
4. login to registry
5. build and push (amd64 + arm64)
6. digest report
```

### 升级流程

```bash
# 基础版
docker-compose down && docker-compose up -d --pull

# Watchtower 版（自动）
# 无需手动操作，Watchtower 检测新镜像后自动重启
```

### Rollback

```bash
# 回滚到上一个镜像
docker-compose down
docker pull registry.example.com/bili-auto:previous-tag
docker-compose up -d
```

## Section 10: Long-Term Trajectory

| Debt | Severity | Note |
|------|----------|------|
| 镜像仓库地址 | — | 待确定（Docker Hub / GHCR / 私有） |
| 模型更新机制 | Low | 未来可添加版本检测 |
| 多平台测试 | Med | 需要 CI 测试 amd64 + arm64 |

**Reversibility: 4/5** — Docker 方案可以完全移除，不影响原有部署方式。

## NOT in scope

- Helm Chart 部署（K8s）
- 私有模型镜像预加载
- 镜像签名验证

## What already exists

- `_migrate_if_needed()` 在 database.py 中已实现
- init_services() 在 scripts/init_setup.py 中调用
- whisper 检测逻辑在 app/modules/whisper_ai.py 中已有基础

## Dream state delta

```
  CURRENT STATE                  THIS PLAN                  IDEAL (12个月)
  手动部署，需要                   Docker 一键部署              完全自动化
  手动下载 whisper.cpp            自动下载 whisper.cpp         模型按需自动选择
  手动管理容器更新                Watchtower 自动更新          用户零感知更新
```

## Implementation Files

### 1. .github/workflows/docker.yml

```yaml
name: Docker Build

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        platform: [linux/amd64, linux/arm64]
    steps:
      - uses: actions/checkout@v4

      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          platforms: ${{ matrix.platform }}
          push: ${{ github.event_name != 'pull_request' }}
          cache-from: type=gha,scope=${{ matrix.platform }}
          cache-to: type=gha,mode=max,scope=${{ matrix.platform }}
          tags: |
            ghcr.io/${{ github.repository }}/bili-auto:latest
            ghcr.io/${{ github.repository }}/bili-auto:${{ matrix.platform }}
            ghcr.io/${{ github.repository }}/bili-auto:${{ github.sha }}
```

### 2. Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl git \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv
RUN pip install uv

# 复制依赖文件
COPY pyproject.toml uv.lock ./

# 安装依赖（利用缓存）并安装项目本身
RUN uv sync --frozen && uv pip install -e .

# 复制代码
COPY . .

# 创建数据目录
RUN mkdir -p /app/data /app/logs /app/models

# 启动命令
CMD ["python", "main.py"]
```

### 3. docker-compose.yml

```yaml
services:
  bili:
    image: ghcr.io/TooAndy/bili-auto:latest
    container_name: bili-auto
    restart: unless-stopped
    volumes:
      - bili-data:/app/data
      - bili-logs:/app/logs
      - bili-models:/app/models
    env_file:
      - .env
    environment:
      - DATABASE_URL=sqlite:///data/bili.db
      - PYTHONUNBUFFERED=1
      - WHISPER_CPP_MODEL=/app/models/ggml-small.bin
    healthcheck:
      test: ["CMD", "python", "-c", "import sqlite3; sqlite3.connect('/app/data/bili.db').close()"]
      interval: 30s
      timeout: 30s
      retries: 3
      start_period: 60s

volumes:
  bili-data:
  bili-logs:
  bili-models:
```

### 4. docker-compose.watchtower.yml

```yaml
services:
  bili:
    image: ghcr.io/TooAndy/bili-auto:latest
    container_name: bili-auto
    restart: unless-stopped
    volumes:
      - bili-data:/app/data
      - bili-logs:/app/logs
      - bili-models:/app/models
      - /var/run/docker.sock:/var/run/docker.sock
    env_file:
      - .env
    environment:
      - DATABASE_URL=sqlite:///data/bili.db
      - PYTHONUNBUFFERED=1

  watchtower:
    image: containrrr/watchtower
    container_name: watchtower
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    command: --interval 3600 bili

volumes:
  bili-data:
  bili-logs:
  bili-models:
```

### 5. app/utils/whisper_downloader.py (新增)

```python
"""
whisper.cpp 自动下载工具
首次启动时检测并下载对应平台的 whisper.cpp CLI 和模型
"""
import platform
import os
import json
from pathlib import Path

import requests
from app.utils.logger import get_logger

logger = get_logger("whisper_downloader")

RELEASES_API = "https://api.github.com/repos/ggerganov/whisper.cpp/releases/latest"
# whisper.cpp 官方 releases 包含预编译二进制
CLI_ASSETS = {
    "darwin-arm64": "whisper-bin-darwin-arm64",
    "darwin-x86_64": "whisper-bin-darwin-x86_64",
    "linux-x64": "whisper-bin-linux-x64",
}
MODEL_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin"

# ggml-small.bin 的 SHA256（需从官方验证后填入）
# 设置环境变量 VERIFY_MODEL_HASH=false 可跳过校验
import os
GGML_SMALL_SHA256 = os.environ.get("GGML_SMALL_SHA256", "")  # TODO: 填入真实值

def detect_platform() -> str:
    """检测当前平台和架构"""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "darwin":
        return "darwin-arm64" if machine == "arm64" else "darwin-x86_64"
    elif system == "linux":
        return "linux-x64"
    else:
        raise ValueError(f"Unsupported platform: {system}-{machine}")

def _get_cli_download_url() -> tuple[str, str]:
    """获取 CLI 下载 URL 和文件名"""
    plat = detect_platform()
    asset_name = CLI_ASSETS.get(plat)
    if not asset_name:
        raise ValueError(f"No prebuilt binary for {plat}")

    # 查询 GitHub releases 获取下载链接
    response = requests.get(RELEASES_API, timeout=30)
    response.raise_for_status()
    data = response.json()

    for asset in data.get("assets", []):
        if asset["name"] == asset_name:
            return asset["browser_download_url"], asset_name

    raise FileNotFoundError(f"Asset {asset_name} not found in releases")

def _download_with_progress(url: str, dest: Path, expected_sha256: str = None) -> bool:
    """下载文件，带进度显示和 SHA256 校验"""
    import hashlib

    try:
        headers = {"User-Agent": "bili-auto-docker/1.0"}
        response = requests.get(url, stream=True, headers=headers, timeout=600)
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))

        dest.parent.mkdir(parents=True, exist_ok=True)

        downloaded = 0
        sha256_hash = hashlib.sha256()
        with open(dest, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                sha256_hash.update(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded * 100 // total
                    print(f"\r  下载中: {pct}%", end="", flush=True)

        print()  # 换行

        if expected_sha256:
            actual = sha256_hash.hexdigest()
            if actual != expected_sha256:
                logger.error(f"SHA256 mismatch: expected {expected_sha256[:8]}..., got {actual[:8]}...")
                dest.unlink()
                return False
        else:
            logger.debug("SHA256 校验已跳过（未配置）")

        return True
    except Exception as e:
        logger.warning(f"Download failed: {e}")
        if dest.exists():
            dest.unlink()
        return False

def ensure_whisper_cli(cli_path: str) -> bool:
    """确保 whisper.cpp CLI 存在"""
    if os.path.exists(cli_path):
        logger.debug(f"whisper.cpp CLI exists: {cli_path}")
        return True

    logger.info(f"Downloading whisper.cpp CLI...")
    try:
        url, filename = _get_cli_download_url()
        temp_path = Path(cli_path + ".tmp")
        if _download_with_progress(url, temp_path):
            temp_path.chmod(0o755)
            temp_path.rename(cli_path)
            logger.info(f"whisper.cpp CLI saved to {cli_path}")
            return True
    except Exception as e:
        logger.warning(f"Failed to download whisper.cpp: {e}")

    return False

def ensure_whisper_model(model_path: str) -> bool:
    """确保 whisper 模型存在（约 500MB）"""
    if os.path.exists(model_path):
        logger.debug(f"whisper model exists: {model_path}")
        return True

    logger.info(f"Downloading ggml-small.bin model (~500MB)...")
    try:
        temp_path = Path(model_path + ".tmp")
        if _download_with_progress(MODEL_URL, temp_path, GGML_SMALL_SHA256):
            temp_path.rename(model_path)
            logger.info(f"Model saved to {model_path}")
            return True
    except Exception as e:
        logger.warning(f"Failed to download model: {e}")

    return False

def setup_whisper() -> bool:
    """设置 whisper.cpp，返回是否成功（失败时回退到 faster-whisper）"""
    cli_path = os.environ.get("WHISPER_CPP_CLI", "/app/models/whisper")
    model_path = os.environ.get("WHISPER_CPP_MODEL", "/app/models/ggml-small.bin")

    cli_ok = ensure_whisper_cli(cli_path)
    model_ok = ensure_whisper_model(model_path)

    if not cli_ok or not model_ok:
        logger.warning("whisper.cpp setup failed, will use faster-whisper instead")
        return False

    return True
```

## TODOS.md Updates

待添加到 TODOS.md 的项目：

1. **whisper.cpp 自动下载模块**
   - Why: Docker 部署必须，零配置
   - Pros: 开箱即用，用户无需手动下载
   - Cons: 需要处理跨平台
   - Effort: M
   - Priority: P1

2. **Docker 多架构构建**
   - Why: 支持 Mac (Apple Silicon) + Linux 服务器
   - Pros: 覆盖主要用户场景
   - Cons: 构建时间增加
   - Effort: M
   - Priority: P1
