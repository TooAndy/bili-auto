FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv
RUN pip install uv

# 复制全部代码
COPY . .

# 安装依赖并安装项目本身
RUN uv sync --frozen && uv pip install -e .

# 创建数据目录
RUN mkdir -p /app/data /app/logs /app/models

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import sqlite3; sqlite3.connect('/app/data/bili.db').close()" || exit 1

# 启动命令
CMD ["python", "main.py"]