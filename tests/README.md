# 测试说明

## 单元测试（默认运行）

运行所有单元测试（不包括集成测试）：

```bash
uv run pytest tests/ -v
```

或者只运行特定模块：

```bash
# 测试下载模块
uv run pytest tests/test_downloader.py -v

# 测试 ASR 模块
uv run pytest tests/test_asr.py -v

# 测试字幕模块
uv run pytest tests/test_subtitle.py -v

# 测试 B站 API 模块
uv run pytest tests/test_bilibili.py -v
```

## 集成测试

集成测试会实际调用模型或 API，需要额外配置。

### 运行集成测试

```bash
# 运行所有集成测试
uv run pytest -m integration -v

# 只运行 Whisper 集成测试
uv run pytest tests/test_asr.py::test_whisper_integration_real_transcribe -v -s

# 只运行 Qwen 集成测试
uv run pytest tests/test_asr.py::test_qwen_integration_real_transcribe -v -s
```

### 集成测试说明

**Whisper 集成测试**
- 首次运行需要下载模型（约 1GB for small 模型）
- 测试用的是 1 秒静音音频，识别结果可能为空

**Qwen ASR 集成测试**
- 需要配置 `.env` 中的 `ASR_API_KEY`
- 需要网络连接
- 会产生 API 调用费用

## Fixtures

测试提供以下 fixtures：

- `temp_dir` - 临时目录
- `sample_wav_path` - 测试用 WAV 文件（1秒静音）
- `mock_config` - mock Config 对象
- `mock_subprocess` - mock subprocess.run
