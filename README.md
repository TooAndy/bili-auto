# B站UP主自动化摘要系统 (bili-auto)

自动化爬取B站UP主的视频和动态，使用Whisper进行语音识别，用LLM生成视频摘要。

## 🎯 项目特点

- **自动化采集**: 定时检测UP主新视频和动态
- **智能摘要**: 使用OpenAI/DeepSeek/通义千问等API生成内容摘要
- **语音识别**: 支持 faster-whisper 和 whisper.cpp 两种方案
- **文本纠错**: LLM 自动修正语音识别错误
- **内容持久化**: 识别文本保存为 txt，详细总结保存为 markdown
- **飞书文档**: 自动上传视频摘要到飞书云盘，按UP主和内容分类
- **灵活推送**: 统一的多渠道推送接口（飞书、Telegram、微信等）
- **Docker 部署**: 一键部署，自动下载 whisper.cpp 模型

## 📁 项目结构

```
bili-auto/
├── app/                    # 核心应用模块
│   ├── modules/           # 功能模块
│   │   ├── bilibili.py   # B站API接口
│   │   ├── downloader.py # 音视频下载（m4a + mp4）
│   │   ├── dynamic.py    # 动态处理
│   │   ├── feishu_docs.py # 飞书文档上传和分类
│   │   ├── processor.py  # 统一处理（纠错+总结）
│   │   ├── push.py       # 消息推送
│   │   ├── subtitle.py   # 字幕获取
│   │   └── whisper_ai.py # 语音识别（faster-whisper + whisper.cpp）
│   ├── models/           # 数据模型
│   │   └── database.py   # SQLAlchemy ORM
│   ├── tools/            # CLI 工具
│   │   └── classification_rules.py # 飞书文档分类规则管理
│   ├── utils/            # 工具函数
│   │   ├── errors.py     # 异常定义
│   │   └── logger.py     # 日志管理
│   ├── queue_worker.py   # 视频任务队列处理
│   └── scheduler.py      # 定时任务调度
├── scripts/              # 实用脚本工具
│   ├── batch_download.py        # 批量下载 UP主视频
│   ├── manage_subscriptions.py  # UP主订阅管理工具
│   ├── migrate_add_doc_url.py    # 数据库迁移（添加文档URL字段）
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
│   ├── video/           # 下载的视频（mp4）
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

### 2. 登录 B站（获取 Cookie 和 refresh_token）

```bash
bili login
```

二维码会推送到已配置的飞书/Telegram频道，也可以在终端看到链接。

**为什么需要登录？**

- Cookie 用于访问 B站 API，检测 UP 主新视频和动态
- `refresh_token` 用于自动刷新 Cookie，避免 Cookie 过期后需要手动重新登录
- 扫码登录获取的 Cookie 和 refresh_token 是配套的，能确保刷新成功

### 3. 配置环境

复制 `.env.example` 为 `.env` 并填入配置：

```bash
cp .env.example .env
# 编辑 .env 配置:
# - OPENAI_API_KEY (支持 OpenAI/DeepSeek/通义千问等)
# - OPENAI_BASE_URL (自定义 API 端点)
# - OPENAI_MODEL (模型名称)
# - BILIBILI_COOKIE (批量下载必须配置，避免限流)
# - VIDEO_CHECK_INTERVAL (视频检测间隔，分钟)
# - DYNAMIC_CHECK_INTERVAL (动态检测间隔，分钟，<=0 禁用)
# - USE_WHISPER_CPP (是否使用 whisper.cpp)
# - WHISPER_CPP_CLI (whisper.cpp 路径)
# - WHISPER_CPP_MODEL (whisper.cpp 模型路径)
# - FEISHU_DOCS_ENABLED (是否启用飞书文档上传)
# - FEISHU_APP_ID / FEISHU_APP_SECRET (飞书应用凭证)
# - FEISHU_DOCS_FOLDER_TOKEN (飞书云盘文件夹 token)
```

### 3. 管理UP主订阅

```bash
bili sub list                 # 查看订阅
bili sub add <mid> <name>      # 添加订阅
bili sub add-bulk              # 批量添加（交互式）
bili sub toggle <mid>          # 启用/禁用
bili sub delete <mid>          # 删除订阅
bili sub update                # 更新视频列表
```

### 4. 管理分类规则（可选）

**方式一：LLM 智能分类（推荐）**
配置文件夹名，让大模型自动分析视频标题并分类：

```bash
# 添加 LLM 分类文件夹
bili-rules add-folder --uploader 呆咪 --folder "每日投资记录"
bili-rules add-folder --uploader 呆咪 --folder "闲聊"

# 列出已配置的 LLM 文件夹
bili-rules list-folders --uploader 呆咪

# 移除文件夹
bili-rules remove-folder --uploader 呆咪 --folder "闲聊"
```

**方式二：正则表达式规则**
手动指定正则表达式匹配模式：

```bash
# 添加分类规则
bili-rules add --uploader 呆咪 --pattern "经济分析" --folder "每周经济分析" --priority 1

# 测试标题匹配
bili-rules test "第1150日投资记录" --uploader 呆咪

# 列出规则
bili-rules list

# 删除规则
bili-rules delete 1
```

详细说明见 [飞书文档分类规则管理](docs/CLASSIFICATION_RULES.md)

### 5. 启动系统

```bash
python main.py
```

## 📂 飞书云盘目录结构

视频摘要会按以下结构上传到飞书云盘：

```
/呆咪/
├── 每日投资记录/
│   └── 2026-04-17_小米年报解读.md
│   └── 2026-04-16_第1150日投资记录.md
├── 每周经济分析/
│   └── 2026-04-15_经济形势分析.md
└── 默认/
    └── 2026-04-10_其他内容.md
```

**分类规则**:

- 支持正则表达式匹配视频标题
- 按优先级排序，数字越小越先匹配
- 无匹配时使用"默认"分类
- 同一UP主的不同内容可以自动分类到不同文件夹

## 📱 推送渠道

### 动态推送

- 检测到新动态后**立即推送**（按发布时间顺序）
- 显示格式：`2026年04月17日 16:30:19`

### 视频推送

- 处理完成后推送到配置的通知渠道

**支持的渠道**:

- 飞书（应用推送）
- Telegram
- 微信企业号（机器人 webhook，不限制 IP）

**配置推送渠道**:

```bash
# 在 .env 中设置，不设置则默认飞书
PUSH_CHANNELS=feishu,telegram,wechat
# 或只启用微信
PUSH_CHANNELS=wechat
```

### 微信企业号配置

使用企业微信机器人，无需配置可信 IP：

```bash
WECHAT_WEBHOOK_KEY=你的机器人webhook_key
```

获取方式：企业微信管理后台 → 应用管理 → 创建机器人 → 复制 webhook 地址中的 key

## 🛠️ 核心工作流

### 视频处理流程

```
scheduler (可配置周期)
    ↓
检测新视频
    ↓
queue_worker
    ├→ 检查已有文本
    ├→ 下载音频/获取字幕
    ├→ 转文字 (Whisper)
    ├→ LLM纠错+总结
    ├→ 保存 txt + markdown
    ├→ 上传到飞书云盘（按分类规则）
    └→ 推送通知
```

### 动态处理流程

```
scheduler (可配置周期)
    ↓
检测新动态
    ↓
按发布时间排序（最早的先推送）
    ↓
立即推送到飞书（无需队列）
```

## ⚙️ 技术栈

- **Python 3.12+**
- **数据库**: SQLite + SQLAlchemy
- **任务调度**: APScheduler
- **语音识别**: faster-whisper / whisper.cpp
- **LLM**: OpenAI API / DeepSeek API / 通义千问 / 本地纯文本fallback
- **飞书**: 文档上传、消息推送
- **日志**: RotatingFileHandler (10MB/5份)

## 📝 常用命令

```bash
# 登录 B站账号
bili login                    # 扫码登录，获取 refresh_token

# 订阅管理
bili sub list                  # 查看订阅列表
bili sub add <mid> <name> [notes]  # 添加订阅
bili sub add-bulk              # 批量添加（交互式）
bili sub toggle <mid>          # 启用/禁用订阅
bili sub delete <mid>          # 删除订阅
bili sub update                # 更新所有订阅的视频列表

# 视频下载
bili download bv <bvid>        # 下载单个视频
bili download up <mid>        # 下载 UP 主所有视频

# 清理工具
bili clear videos              # 清理视频记录

# 测试推送渠道
bili test all                  # 测试所有渠道
bili test feishu               # 测试飞书
bili test wechat               # 测试微信

# 管理分类规则
bili-rules add --uploader 呆咪 --pattern "投资记录" --folder "每日投资记录"

# 测试 ASR 识别
python scripts/test_asr_file.py
```

### 推送渠道配置

通过 `PUSH_CHANNELS` 环境变量配置启用的渠道：

```bash
# 默认只飞书（不设置时）
PUSH_CHANNELS=feishu

# 多个渠道
PUSH_CHANNELS=feishu,telegram,wechat

# 只微信
PUSH_CHANNELS=wechat

# 关闭所有推送（留空）
PUSH_CHANNELS=
```

## 🐛 调试

查看实时日志：

```bash
tail -f logs/bili.log
```

查看特定级别日志：

```bash
grep "ERROR" logs/bili.log
grep "DEBUG" logs/bili.log
grep "新动态" logs/bili.log
```

## 🐳 Docker 部署

### 快速开始

```bash
# 下载镜像
docker pull ghcr.io/tooandy/bili-auto:latest

# 创建配置目录
mkdir -p $(pwd)/bili-data

# 创建配置文件
cat > $(pwd)/.env << 'EOF'
# B站 Cookie（必需）
BILIBILI_COOKIE=your_cookie_here

# LLM 配置（必需）
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.openai.com
OPENAI_MODEL=gpt-4o-mini

# 飞书推送（可选）
FEISHU_WEBHOOK=your_webhook_url
EOF

# 启动容器
docker run -d \
  --name bili-auto \
  --restart unless-stopped \
  -v $(pwd)/bili-data:/app/data \
  -v $(pwd)/.env:/app/.env \
  ghcr.io/tooandy/bili-auto:latest
```

### 数据持久化

| 路径 | 说明 |
|------|------|
| `/app/data` | 数据库和运行时数据 |
| `/app/models` | whisper.cpp 模型（自动下载） |
| `/app/logs` | 日志目录 |

### whisper.cpp 自动下载

首次启动时自动下载 whisper.cpp CLI 和模型（约 500MB）：

- 自动检测平台：darwin-arm64（Apple Silicon）、darwin-x86_64（Intel Mac）、linux-x64
- 模型文件：`ggml-small.bin`
- 下载完成前使用 faster-whisper 作为备选

### 升级

```bash
docker pull ghcr.io/tooandy/bili-auto:latest
docker restart bili-auto
```

或使用 Watchtower 自动更新（见 docker-compose.watchtower.yml）

## 📄 许可证

MIT

---

**项目阶段**: MVP Phase 1 + 优化增强
**最后更新**: 2026年4月17日
**版本**: 1.0.0
