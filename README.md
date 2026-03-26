# B站UP主自动化摘要系统 (bili-auto)

自动化爬取B站UP主的视频和动态，使用Whisper进行语音识别，用LLM生成视频摘要。

## 🎯 项目特点

- **自动化采集**: 定时检测UP主新视频和动态
- **智能摘要**: 使用OpenAI/DeepSeek/通义千问等API生成内容摘要
- **语音识别**: 支持 faster-whisper 和 whisper.cpp 两种方案
- **文本纠错**: LLM 自动修正语音识别错误
- **内容持久化**: 识别文本保存为 txt，详细总结保存为 markdown
- **灵活推送**: 统一的多渠道推送接口（扩展中）

## 📁 项目结构

```
bili-auto/
├── app/                    # 核心应用模块
│   ├── modules/           # 功能模块
│   │   ├── bilibili.py   # B站API接口
│   │   ├── downloader.py # 音视频下载（m4a 格式）
│   │   ├── dynamic.py    # 动态处理
│   │   ├── processor.py  # 统一处理（纠错+总结）
│   │   ├── push.py       # 消息推送
│   │   ├── subtitle.py   # 字幕获取
│   │   └── whisper_ai.py # 语音识别（faster-whisper + whisper.cpp）
│   ├── models/           # 数据模型
│   │   └── database.py   # SQLAlchemy ORM
│   ├── utils/            # 工具函数
│   │   ├── errors.py     # 异常定义
│   │   └── logger.py     # 日志管理
│   ├── queue_worker.py   # 任务队列处理
│   └── scheduler.py      # 定时任务调度
├── scripts/              # 实用脚本工具
│   ├── manage_subscriptions.py  # UP主订阅管理工具
│   ├── reset_processing.py      # 重置 processing 状态
│   ├── test_asr_file.py        # 测试 ASR 识别
│   └── test_processor.py       # 测试统一处理模块
├── docs/                 # 项目文档
│   ├── PROJECT_PLAN.md   # 详细项目规划
│   ├── STATUS_REPORT.md  # 当前状态报告
│   ├── MANAGE_SUBSCRIPTIONS.md  # 订阅管理指南
│   └── QUICK_REFERENCE.md       # 快速参考
├── demo/                 # 示例文件
│   └── prompt.txt        # LLM 提示词模板
├── data/                 # 数据目录
│   ├── audio/           # 下载的音频（m4a）
│   ├── text/            # 识别文本保存
│   ├── markdown/        # 详细总结保存（Markdown）
│   └── bili.db         # 数据库
├── logs/                # 日志目录
├── config.py            # 主配置文件
├── main.py              # 程序入口
├── pyproject.toml       # 依赖配置
├── .env                 # 环境变量（本地）
└── .env.example        # 环境变量示例
```

## 🚀 快速开始

### 1. 安装依赖

```bash
uv sync
```

### 2. 配置环境

复制 `.env.example` 为 `.env` 并填入配置：

```bash
cp .env.example .env
# 编辑 .env 配置:
# - OPENAI_API_KEY (支持 OpenAI/DeepSeek/通义千问等)
# - OPENAI_BASE_URL (自定义 API 端点)
# - OPENAI_MODEL (模型名称)
# - BILIBILI_COOKIE (可选，避免限流)
# - VIDEO_CHECK_INTERVAL (视频检测间隔，分钟)
# - DYNAMIC_CHECK_INTERVAL (动态检测间隔，分钟，<=0 禁用)
# - USE_WHISPER_CPP (是否使用 whisper.cpp)
# - WHISPER_CPP_CLI (whisper.cpp 路径)
# - WHISPER_CPP_MODEL (whisper.cpp 模型路径)
```

### 3. 管理UP主订阅

```bash
uv run python scripts/manage_subscriptions.py
```

详细说明见 [UP主订阅管理指南](docs/MANAGE_SUBSCRIPTIONS.md)

### 4. 启动系统

```bash
uv run python main.py
```

### 5. 实用工具

```bash
# 重置 processing 状态的任务
uv run scripts/reset_processing.py

# 测试 ASR 识别
uv run scripts/test_asr_file.py

# 测试统一处理模块
uv run scripts/test_processor.py
```

## 📖 文档导航

- [项目规划](docs/PROJECT_PLAN.md) - 功能需求和实现方案
- [状态报告](docs/STATUS_REPORT.md) - 当前功能完成情况
- [订阅管理](docs/MANAGE_SUBSCRIPTIONS.md) - 添加/编辑UP主的三种方式
- [快速参考](docs/QUICK_REFERENCE.md) - 常用命令速查表

## 🛠️ 核心工作流

```
scheduler (可配置周期)
    ↓
检测新视频/动态
    ↓
queue_worker (先标记为 processing，避免重复处理)
    ├→ 视频: 检查已有文本 → 下载音频/获取字幕 → 转文字 → LLM纠错+总结 → 保存txt+markdown → 推送
    └→ 动态: 获取 → 下载图片 → 过滤 → 推送
```

## ⚙️ 技术栈

- **Python 3.10+**
- **数据库**: SQLite + SQLAlchemy
- **任务调度**: APScheduler
- **语音识别**: faster-whisper / whisper.cpp
- **LLM**: OpenAI API / DeepSeek API / 通义千问 / 本地纯文本fallback
- **日志**: RotatingFileHandler (10MB/5份)

## 📝 使用示例

### 添加UP主订阅

```bash
# 交互式添加
uv run scripts/manage_subscriptions.py

# 命令行添加
uv run python -c "from scripts.manage_subscriptions import add_subscription; add_subscription(1988098633, '李毓佳')"
```

### 查看当前订阅

```bash
uv run scripts/manage_subscriptions.py  # 选择菜单 1
```

## 🔄 状态机设计

任务处理采用状态机管理：

```
pending (待处理)
    ↓
processing (处理中) - 提交任务前立即设置，避免重复处理
    ↓
done (完成) 或 failed (失败)
```

失败任务自动重试，最多3次。

## 📋 数据库表

- **Subscription**: UP主信息和订阅状态
- **Video**: 视频元数据和处理状态
- **Dynamic**: 动态内容和处理状态
- **Summary**: AI生成的摘要缓存
- **Log**: 系统日志记录

## 🐛 调试

查看实时日志：

```bash
tail -f logs/bili.log
```

查看特定级别日志：

```bash
grep "ERROR" logs/bili.log
grep "DEBUG" logs/bili.log
```

重置 processing 状态任务：

```bash
uv run scripts/reset_processing.py
```

## 📄 许可证

MIT

---

**项目阶段**: MVP Phase 1 + 优化增强
**最后更新**: 2026年3月26日
**版本**: 0.2.0
