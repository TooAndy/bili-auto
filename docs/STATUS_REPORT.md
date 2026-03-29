# 项目状态报告

**项目名**: B站UP主自动化摘要系统
**报告时间**: 2026年3月26日
**阶段**: MVP 核心功能完成（阶段一）+ 优化增强

---

## ✅ 已完成功能清单

### 1. 基础框架
- ✅ 项目目录结构完整
- ✅ 配置管理系统（config.py + .env）
- ✅ 日志系统（rotating file logger）
- ✅ 数据库初始化（SQLite + SQLAlchemy ORM）
- ✅ 错误处理框架
- ✅ 可配置的调度间隔（.env 中 VIDEO_CHECK_INTERVAL, DYNAMIC_CHECK_INTERVAL）

### 2. 核心模块

#### 📺 B站视频处理
- ✅ 视频列表获取 (`bilibili.py`)
  - 支持按 UP 主 ID 获取最新视频
  - 支持 WBI 签名接口，减少限流风险
  - 支持字幕信息查询
  - 支持 Cookie 配置以避免限流
  - WBI 签名器 (`wbi.py`)
    - 自动获取混合密钥
    - 参数签名生成 w_rid
    - 密钥缓存机制

- ✅ 字幕获取 (`subtitle.py`)
  - B站 API 字幕拉取
  - 字幕 JSON 格式解析
  - 支持多国语言字幕

- ✅ 音视频下载 (`downloader.py`)
  - yt-dlp 集成
  - **视频下载（mp4 格式）**，支持多种清晰度（4K, high, 1080P, 720P, 480P）
  - **音频下载（m4a 格式，128k）**，节省空间
  - **从视频提取音频**（ffmpeg），支持视频文件直接进行语音识别
  - 兼容旧的 wav/mp3 文件
  - 本地文件管理

- ✅ 音频转写 (`whisper_ai.py`)
  - faster-whisper 模型集成
  - **whisper.cpp 支持**（可选，通过 .env 配置）
  - CPU 推理支持
  - 中文识别优化
  - 自动格式转换（非 wav 格式用 ffmpeg 转换）

#### 📝 B站动态处理
- ✅ 动态获取 (`dynamic.py`)
  - 动态 API 拉取
  - 多种动态类型支持 (图文、视频等)
  - 图片批量下载

- ✅ 动态过滤
  - 转发/链接识别
  - 垃圾内容过滤
  - 最小长度检查

#### 🤖 LLM 内容处理
- ✅ 统一处理模块 (`processor.py`)
  - **纠错 + 总结一次 API 调用完成**
  - OpenAI API 支持（兼容 DeepSeek、通义千问等）
  - 本地回退方案（纯文本分析）
  - 结构化 JSON 输出
  - 从 demo/prompt.txt 加载提示词

- ✅ 摘要格式
  ```json
  {
    "summary": "50-100 字核心观点",
    "details": "详细总结大纲",
    "key_points": ["观点1", "观点2", ...],
    "tags": ["标签1", "标签2", ...],
    "insights": "深层洞察",
    "duration_minutes": 0
  }
  ```

- ✅ 内容持久化
  - 识别文本保存到 `data/text/{bvid}.txt`
  - 详细总结保存到 `data/markdown/{bvid}.md`（Markdown 格式）
  - 如果已有文本文件，跳过下载和识别

### 3. 定时任务与队列

- ✅ 调度器 (`scheduler.py`)
  - 视频检测：可配置（默认 10 分钟）
  - 动态检测：可配置（默认 5 分钟）
  - 间隔 <= 0 时禁用检测
  - 错误处理与日志记录
  - 数据库状态追踪

- ✅ 队列处理 (`queue_worker.py`)
  - 并发处理（3 worker）
  - 视频完整流程：字幕/视频 → Whisper（支持视频输入） → LLM（纠错+总结） → 推送
  - **优先检查视频文件**，兼容音频文件
  - 动态简化流程：过滤 → 推送
  - 失败重试机制（最多 3 次）
  - 状态机管理：pending → processing → done/failed
  - **修复重复处理问题**：提交任务前先更新状态为 processing

### 4. 数据管理

- ✅ 数据库表设计
  - `subscriptions`: UP 主订阅表
  - `videos`: 视频表（含摘要 JSON、视频路径、音频路径）
  - `dynamics`: 动态表（含图片路径）
  - `summaries`: 摘要表（备用）
  - `logs`: 日志表（可选）

- ✅ 状态追踪
  - 视频状态：pending|processing|done|failed
  - 动态状态：pending|processing|sent|filtered|failed
  - 尝试计数与错误信息记录

### 5. 推送系统（框架就绪）

- ✅ 推送接口设计 (`push.py`)
  - 统一的 `push_content()` 入口
  - 支持多渠道配置
  - **当前为占位符（用户要求先不实现推送）**
  - 包含未来推送方案的完整代码注释

### 6. 实用脚本

- ✅ `scripts/batch_download.py` - 批量下载 UP主视频
  - 支持下载所有视频或按日期范围过滤
  - 支持多种清晰度选择（4K, high, 1080P, 720P, 480P）
  - 自动添加到数据库并触发处理流程
  - 支持预览模式和强制重新处理
- ✅ `scripts/manage_subscriptions.py` - UP主订阅管理
- ✅ `scripts/reset_processing.py` - 重置 processing 状态任务
- ✅ `scripts/test_asr_file.py` - 测试 ASR 识别
- ✅ `scripts/test_processor.py` - 测试统一处理模块
- ✅ `scripts/reset_videos.py` - 重置视频状态（旧脚本）
- ✅ `scripts/test_asr.py` - 旧 ASR 测试（保留）

### 7. 测试覆盖

- ✅ 完整单元测试 (`tests/`)
  - `test_asr.py` - Whisper 识别测试
  - `test_bilibili.py` - B站 API 测试
  - `test_downloader.py` - 下载器测试
  - `test_subtitle.py` - 字幕获取测试
  - `conftest.py` - pytest fixtures

### 8. 批量下载功能

- ✅ 批量下载 UP主所有视频
  - 支持日期范围过滤
  - 支持多种清晰度选择
  - 预览模式
  - 强制重新处理
  - 自动入库并触发处理流程

**使用示例：**
```bash
# 下载所有视频（默认最高清晰度）
uv run scripts/batch_download.py 1988098633 --all

# 按日期范围下载
uv run scripts/batch_download.py 1988098633 --start-date 20250101 --end-date 20250331

# 预览模式
uv run scripts/batch_download.py 1988098633 --all --preview

# 指定清晰度
uv run scripts/batch_download.py 1988098633 --all --quality 1080p

# 强制重新处理已存在的视频
uv run scripts/batch_download.py 1988098633 --all --force
```

**清晰度选项：**
- `4k` - 4K (2160P)
- `high` - 最高可用（默认）
- `1080p` - 1080P
- `720p` - 720P
- `480p` - 480P
- `360p` - 360P

---

## 📊 测试验证

### 初始化测试
```
✅ 目录创建成功
✅ 数据库初始化成功
✅ 日志系统就绪
```

### 数据库测试
```
✅ 添加 UP 主订阅成功
✅ 模型关系正确
✅ 状态管理完整
```

### LLM 模块测试
```
✅ 本地摘要生成正常
✅ JSON 结构化输出正确
✅ 错误处理与回退完整
✅ 纠错+总结统一处理正常
```

---

## 🚀 快速启动

### 1. 环境初始化
```bash
cd /Users/aniss/Code/bili-auto
uv run python scripts/manage_subscriptions.py
```

### 2. 配置环境变量
```bash
# .env 已预配置
OPENAI_API_KEY=sk-xxxx
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=deepseek-r1-distill-qwen-32b
BILIBILI_COOKIE=xxxxx  # 可选，避免限流

# 调度间隔（分钟），<=0 禁用
VIDEO_CHECK_INTERVAL=10
DYNAMIC_CHECK_INTERVAL=-1

# Whisper 配置
WHISPER_MODEL=small
WHISPER_DEVICE=cpu

# Whisper.cpp（可选）
USE_WHISPER_CPP=true
WHISPER_CPP_CLI=/path/to/whisper-cli
WHISPER_CPP_MODEL=/path/to/ggml-small.bin
```

### 3. 数据库初始化
```bash
# 使用 manage_subscriptions.py 添加 UP 主
uv run python scripts/manage_subscriptions.py
```

### 4. 启动系统
```bash
uv run python main.py
```

### 5. 监控日志
```bash
tail -f logs/bili.log
```

### 6. 重置 processing 状态（如需要）
```bash
uv run scripts/reset_processing.py
```

---

## 📁 项目结构

```
bili-auto/
├── main.py                    # 入口
├── config.py                  # 配置
├── .env                       # 环境变量（已配置）
├── .env.example              # 环境变量示例
├── pyproject.toml            # 依赖管理
├── pytest.ini                # pytest 配置
│
├── app/
│   ├── scheduler.py          # 定时检测（视频 + 动态）
│   ├── queue_worker.py       # 队列处理引擎
│   │
│   ├── modules/
│   │   ├── bilibili.py       # 视频获取
│   │   ├── dynamic.py        # 动态获取 + 过滤
│   │   ├── downloader.py     # 音频下载（m4a）
│   │   ├── subtitle.py       # 字幕获取
│   │   ├── whisper_ai.py     # 音频转写（faster-whisper + whisper.cpp）
│   │   ├── processor.py      # 统一处理（纠错 + 总结）
│   │   ├── asr.py           # ❌ 已删除
│   │   ├── correction.py     # ❌ 已删除
│   │   ├── llm.py           # ❌ 已删除
│   │   └── push.py           # 推送接口（占位符）
│   │
│   ├── models/
│   │   └── database.py       # ORM 模型
│   │
│   └── utils/
│       ├── logger.py         # 日志配置
│       └── errors.py         # 错误定义
│
├── scripts/
│   ├── batch_download.py       # 批量下载 UP主视频
│   ├── manage_subscriptions.py  # UP主订阅管理
│   ├── reset_processing.py      # 重置 processing 状态
│   ├── test_asr_file.py        # 测试 ASR 识别
│   ├── test_processor.py       # 测试统一处理模块
│   ├── reset_videos.py         # 旧脚本（保留）
│   └── test_asr.py            # 旧脚本（保留）
│
├── tests/                   # 单元测试
│   ├── conftest.py
│   ├── test_asr.py
│   ├── test_bilibili.py
│   ├── test_downloader.py
│   └── test_subtitle.py
│
├── demo/                    # 示例文件
│   └── prompt.txt          # LLM 提示词模板
│
├── data/
│   ├── video/              # 视频文件（mp4）
│   ├── audio/              # 音频文件（m4a）
│   ├── text/               # 识别文本保存
│   ├── markdown/           # 详细总结保存（Markdown）
│   └── bili.db             # 数据库
│
└── logs/
    └── bili.log             # 应用日志
```

---

## 🔄 工作流程

### 视频处理流程
```
1. 调度器定时检测（可配置间隔）或批量下载工具
   ↓
2. 获取UP主最新视频列表
   ↓
3. 新视频添加到数据库 (status='pending')
   ↓
4. 队列处理器拾取待处理视频，先标记为 processing
   ↓
5. 检查 data/text/{bvid}.txt 是否存在
   ├─ 存在 → 直接读取使用
   └─ 不存在 → 检查媒体文件
       ├─ 优先检查 data/video/{bvid}.mp4（视频）
       └─ 其次检查 data/audio/{bvid}.m4a（音频）
   ↓
6. 获取字幕或使用 Whisper 转写（支持视频直接提取音频）
   ↓
7. LLM 统一处理（纠错 + 总结）
   ↓
8. 保存文本到 data/text/，保存详情到 data/markdown/
   ↓
9. 推送到配置的渠道（当前为占位符）
   ↓
10. 更新数据库状态 (status='done'/'failed')
```

### 动态处理流程
```
1. 调度器定时检测（可配置间隔）
   ↓
2. 获取UP主最新动态
   ↓
3. 下载动态中的所有图片
   ↓
4. 新动态添加到数据库 (status='pending')
   ↓
5. 队列处理器拾取待处理动态，先标记为 processing
   ↓
6. 内容预过滤（去重、反垃圾）
   ↓
7. 推送到配置的渠道（当前为占位符）
   ↓
8. 更新数据库状态 (status='sent'/'filtered'/'failed')
```

---

## ⚙️ 配置说明

### .env 配置项
```
# B站会话
BILIBILI_COOKIE=  # 可选，避免限流

# 大语言模型
OPENAI_API_KEY=   # 支持 OpenAI、Azure、DeepSeek、通义千问等
OPENAI_BASE_URL=  # 自定义 API 端点
OPENAI_MODEL=     # 默认 gpt-3.5-turbo

# 调度间隔（分钟），<=0 禁用
VIDEO_CHECK_INTERVAL=10
DYNAMIC_CHECK_INTERVAL=-1

# Whisper 语音识别
WHISPER_MODEL=small|base|tiny|medium|large
WHISPER_DEVICE=cpu|cuda

# Whisper.cpp（可选，更快）
USE_WHISPER_CPP=true
WHISPER_CPP_CLI=/path/to/whisper-cli
WHISPER_CPP_MODEL=/path/to/ggml-small.bin

# 推送渠道（当前不启用）
FEISHU_WEBHOOK=   # 飞书机器人 webhook
TELEGRAM_TOKEN=   # Telegram 机器人 token
TELEGRAM_CHAT_ID= # 接收消息的 chat ID
WECHAT_*=         # 微信企业号配置

# 数据库
DATABASE_URL=sqlite:///data/bili.db

# 日志
LOG_LEVEL=INFO
```

---

## 📋 阶段二计划（工程质量）

- [ ] 错误处理详细化
- [ ] 性能监控面板
- [ ] 数据库连接池优化
- [ ] 日志聚合方案
- [ ] 监控告警机制
- [ ] Systemd 服务配置

---

## 📋 阶段三计划（产品化）

- [ ] 关键词过滤引擎
- [ ] 内容分类器
- [ ] 向量搜索（知识库）
- [ ] Web 管理后台（可选）
- [ ] 推送集成（飞书、Telegram、微信）
- [ ] 成本优化（本地开源模型）

---

## 🐛 已知限制

1. **Whisper 模型下载**: 首次运行需下载 ~1GB 模型文件，建议提前下载
2. **B站 API 限流**: 频繁请求会被限速，建议配置 Cookie 增加频率
3. **字幕丢失**: 部分老视频或无字幕视频需依赖 Whisper
4. **推送功能**: 当前为占位符，等待后续阶段实现
5. **音频格式**: 已改用 m4a 节省空间，whisper.cpp 需要 ffmpeg 转换

---

## 📞 后续支持

- 系统运行遇到问题，查阅 `logs/bili.log`
- API 限流，请更新 `BILIBILI_COOKIE`
- 摘要质量差，可升级到更好的模型或调整 prompt
- 推送功能需求，见 `app/modules/push.py` 注释
- 任务卡在 processing 状态，运行 `scripts/reset_processing.py`

---

**项目已准备好进入试运行阶段！** 🎉
