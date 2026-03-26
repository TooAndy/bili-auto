# B站UP主自动化摘要系统 (bili-auto)

自动化爬取B站UP主的视频和动态，使用Whisper进行语音识别，用LLM生成视频摘要。

## 🎯 项目特点

- **自动化采集**: 定时检测UP主新视频和动态
- **智能摘要**: 使用OpenAI/DeepSeek API或本地模型生成内容摘要  
- **语音识别**: 采用faster-whisper进行高效的中文语音转文字
- **灵活推送**: 统一的多渠道推送接口（扩展中）

## 📁 项目结构

```
bili-auto/
├── app/                    # 核心应用模块
│   ├── modules/           # 功能模块
│   │   ├── bilibili.py   # B站API接口
│   │   ├── downloader.py # 音视频下载
│   │   ├── dynamic.py    # 动态处理
│   │   ├── llm.py        # AI摘要生成
│   │   ├── push.py       # 消息推送
│   │   ├── subtitle.py   # 字幕获取
│   │   └── whisper_ai.py # 语音识别
│   ├── models/           # 数据模型
│   │   └── database.py   # SQLAlchemy ORM
│   ├── utils/            # 工具函数
│   │   ├── errors.py     # 异常定义
│   │   └── logger.py     # 日志管理
│   ├── queue_worker.py   # 任务队列处理
│   └── scheduler.py      # 定时任务调度
├── scripts/              # 实用脚本工具
│   ├── manage_subscriptions.py  # [UP主订阅管理工具](scripts/manage_subscriptions.py)
│   └── init_setup.py            # 初始化脚本
├── docs/                 # 项目文档
│   ├── PROJECT_PLAN.md   # 详细项目规划
│   ├── STATUS_REPORT.md  # 当前状态报告
│   ├── MANAGE_SUBSCRIPTIONS.md  # 订阅管理指南
│   └── QUICK_REFERENCE.md       # 快速参考
├── examples/             # 示例配置
├── data/                 # 数据目录
│   ├── audio/           # 下载的音频
│   ├── dynamic_images/  # 动态图片
│   └── subtitles/       # 字幕文件
├── logs/                # 日志目录
├── config.py            # 主配置文件
├── main.py              # 程序入口
├── pyproject.toml       # 依赖配置
└── .env                 # 环境变量（本地）
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r pyproject.toml
```

### 2. 配置环境

复制 `.env.example` 为 `.env` 并填入配置：

```bash
cp .env.example .env
# 编辑 .env 配置:
# - OPENAI_API_KEY (可选，支持本地fallback)
# - DEEPSEEK_API_KEY (可选)
```

### 3. 初始化数据库

```bash
python scripts/init_setup.py
```

### 4. 管理UP主订阅

```bash
python scripts/manage_subscriptions.py
```

详细说明见 [UP主订阅管理指南](docs/MANAGE_SUBSCRIPTIONS.md)

### 5. 启动系统

```bash
python main.py
```

## 📖 文档导航

- [项目规划](docs/PROJECT_PLAN.md) - 功能需求和实现方案
- [状态报告](docs/STATUS_REPORT.md) - 当前功能完成情况
- [订阅管理](docs/MANAGE_SUBSCRIPTIONS.md) - 添加/编辑UP主的三种方式
- [快速参考](docs/QUICK_REFERENCE.md) - 常用命令速查表

## 🛠️ 核心工作流

```
scheduler (10分钟周期)
    ↓
检测新视频/动态
    ↓
queue_worker
    ├→ 视频: 下载 → 字幕 → 转文字 → LLM摘要 → 推送
    └→ 动态: 获取 → 下载图片 → 过滤 → 推送
```

## ⚙️ 技术栈

- **Python 3.10+**
- **数据库**: SQLite + SQLAlchemy
- **任务调度**: APScheduler
- **语音识别**: faster-whisper
- **LLM**: OpenAI API / DeepSeek API / 本地纯文本fallback
- **日志**: RotatingFileHandler (10MB/5份)

## 📝 使用示例

### 添加UP主订阅

```bash
# 交互式添加
python scripts/manage_subscriptions.py

# 命令行添加  
python -c "from scripts.manage_subscriptions import add_subscription; add_subscription(1988098633, '李毓佳')"
```

### 查看当前订阅

```bash
python scripts/manage_subscriptions.py  # 选择菜单 1
```

## 🔄 状态机设计

任务处理采用状态机管理：

```
pending (待处理)
    ↓
processing (处理中) 
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
tail -f logs/bili_auto.log
```

查看特定级别日志：

```bash
grep "ERROR" logs/bili_auto.log
grep "DEBUG" logs/bili_auto.log
```

## 📄 许可证

MIT

---

**项目阶段**: MVP Phase 1 - 核心功能完成    
**最后更新**: 2024年3月  
**版本**: 0.1.0
