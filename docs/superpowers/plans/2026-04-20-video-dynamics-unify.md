# 动态视频统一检测实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用动态检测（每1分钟）替代视频检测（每10分钟），消除冗余 API 调用，补全直播回放检测。

**Architecture:** 在 `check_new_dynamics()` 中，当检测到 `DYNAMIC_TYPE_AV` 或 `MAJOR_TYPE_ARCHIVE` 视频动态时，同时创建 `Dynamic` 和 `Video` 两条记录。动态立即推送；Video 由 `queue_worker` 异步处理完整流水线。

**Tech Stack:** Python, SQLAlchemy, SQLite

---

## 文件变更总览

| 文件 | 改动 |
|------|------|
| `app/models/database.py` | Dynamic 表新增 video_bvid 字段 |
| `app/modules/dynamic.py` | `_parse_dynamic()` 提取 bvid |
| `app/scheduler.py` | 创建 Video 记录；移除 check_new_videos 调度 |

---

## Task 1: 数据库新增 video_bvid 字段

**文件:** `app/models/database.py:58-78`

**目标:** Dynamic 表新增 `video_bvid = Column(String, nullable=True)` 字段。

- [ ] **Step 1: 查看当前 Dynamic 模型定义**

```python
# app/models/database.py 第 58-78 行
class Dynamic(Base):
    """动态表"""
    __tablename__ = "dynamics"
    # 现有字段...
```

- [ ] **Step 2: 添加 video_bvid 字段**

在 `mid` 字段后添加：
```python
video_bvid = Column(String, nullable=True)  # 关联视频的 bvid（视频动态时填充）
```

- [ ] **Step 3: 运行数据库迁移**

```bash
uv run python -c "
from app.models.database import engine, Base
from sqlalchemy import inspect
inspector = inspect(engine)
cols = [c['name'] for c in inspector.get_columns('dynamics')]
if 'video_bvid' not in cols:
    with engine.connect() as conn:
        conn.execute('ALTER TABLE dynamics ADD COLUMN video_bvid VARCHAR')
        conn.commit()
    print('migration done')
else:
    print('video_bvid already exists')
"
```

预期输出: `migration done`

- [ ] **Step 4: 验证字段存在**

```bash
uv run python -c "
from sqlalchemy import inspect
from app.models.database import engine
cols = [c['name'] for c in inspect(engine).get_columns('dynamics')]
print('video_bvid' in cols)
"
```

预期输出: `True`

---

## Task 2: _parse_dynamic() 提取视频 bvid

**文件:** `app/modules/dynamic.py:132-161`

**目标:** `MAJOR_TYPE_ARCHIVE` 和 `DYNAMIC_TYPE_AV` 分支提取 `bvid` 并存入返回字典。

- [ ] **Step 1: 查看现有代码结构**

第 132-136 行 `MAJOR_TYPE_ARCHIVE` 分支和第 157-161 行 `DYNAMIC_TYPE_AV` 兼容分支。

- [ ] **Step 2: 修改 MAJOR_TYPE_ARCHIVE 分支（新增 bvid 提取）**

```python
# app/modules/dynamic.py 第 133-136 行
# 原来:
elif major_type == "MAJOR_TYPE_ARCHIVE":
    archive = major.get("archive") or {}
    title = archive.get("title", "")
    text = archive.get("desc", "")

# 改为:
elif major_type == "MAJOR_TYPE_ARCHIVE":
    archive = major.get("archive") or {}
    title = archive.get("title", "")
    text = archive.get("desc", "")
    bvid = archive.get("bvid")  # 新增
```

- [ ] **Step 3: 修改 DYNAMIC_TYPE_AV 兼容分支（新增 bvid 提取）**

```python
# app/modules/dynamic.py 第 157-161 行
# 原来:
if dynamic_type_str == "DYNAMIC_TYPE_AV":
    archive = major.get("archive") or {}
    title = archive.get("title", "")
    desc = archive.get("desc", "")

# 改为:
if dynamic_type_str == "DYNAMIC_TYPE_AV":
    archive = major.get("archive") or {}
    title = archive.get("title", "")
    desc = archive.get("desc", "")
    bvid = archive.get("bvid")  # 新增
```

- [ ] **Step 4: 修改返回值，加入 bvid**

```python
# app/modules/dynamic.py 第 196-205 行
# 原来返回值:
return {
    "dynamic_id": dynamic_id,
    "type": dynamic_type_str,
    "title": title,
    "text": text,
    "image_urls": image_urls,
    "pub_time": pub_datetime,
    "pub_ts": pub_ts,
    "images": []
}

# 改为（在 return 之前添加 bvid 处理）:
# 将 bvid 合并到返回字典
result = {
    "dynamic_id": dynamic_id,
    "type": dynamic_type_str,
    "title": title,
    "text": text,
    "image_urls": image_urls,
    "pub_time": pub_datetime,
    "pub_ts": pub_ts,
    "images": []
}
# bvid 可能来自 MAJOR_TYPE_ARCHIVE 或 DYNAMIC_TYPE_AV 分支
if bvid:
    result["bvid"] = bvid
return result
```

- [ ] **Step 5: 写单元测试验证**

```bash
cat > tests/unit/test_dynamic_parser.py << 'EOF'
import pytest
import sys
sys.path.insert(0, '.')
from app.modules.dynamic import DynamicFetcher

def test_parse_av_dynamic_extracts_bvid():
    """DYNAMIC_TYPE_AV 动态应提取 bvid"""
    fetcher = DynamicFetcher()
    
    # 模拟包含 bvid 的 MAJOR_TYPE_ARCHIVE 数据
    item = {
        "id_str": "1234567890",
        "type": "DYNAMIC_TYPE_AV",
        "modules": {
            "module_author": {"pub_ts": "1713000000", "pub_time": "2024-04-13"},
            "module_dynamic": {
                "major": {
                    "type": "MAJOR_TYPE_ARCHIVE",
                    "archive": {
                        "bvid": "BV1TEST12345",
                        "title": "测试视频",
                        "desc": "测试描述"
                    }
                }
            }
        }
    }
    
    result = fetcher._parse_dynamic(item)
    assert result is not None
    assert result.get("bvid") == "BV1TEST12345"
    assert result.get("title") == "测试视频"

def test_parse_non_video_dynamic_no_bvid():
    """非视频动态不应有 bvid"""
    fetcher = DynamicFetcher()
    
    item = {
        "id_str": "2234567890",
        "type": "DYNAMIC_TYPE_DRAW",
        "modules": {
            "module_author": {"pub_ts": "1713000000", "pub_time": "2024-04-13"},
            "module_dynamic": {
                "major": {
                    "type": "MAJOR_TYPE_COMMON",
                    "common": {"desc": "普通文字"}
                }
            }
        }
    }
    
    result = fetcher._parse_dynamic(item)
    assert result is not None
    assert "bvid" not in result
EOF
```

- [ ] **Step 6: 运行测试**

```bash
uv run pytest tests/unit/test_dynamic_parser.py -v
```

预期: PASS

- [ ] **Step 7: 提交**

```bash
git add app/models/database.py app/modules/dynamic.py tests/unit/test_dynamic_parser.py
git commit -m "feat: extract bvid from video dynamics in _parse_dynamic"
```

---

## Task 3: check_new_dynamics() 创建 Video 记录

**文件:** `app/scheduler.py:115-199`

**目标:** 当检测到视频动态（bvid 存在）时，同时创建 Video 记录。

- [ ] **Step 1: 查看 check_new_dynamics 中的循环结构**

第 139-152 行处理每个动态的循环，找到创建 Dynamic 记录的位置。

- [ ] **Step 2: 在创建 Dynamic 记录后，添加 Video 创建逻辑**

在第 167-180 行 Dynamic 创建之后，添加：

```python
# 第 180 行 db.add(new_dynamic) 之后添加:
# 如果是视频动态，同时创建 Video 记录
if dyn.get("bvid"):
    existing_video = db.query(Video).filter_by(bvid=dyn["bvid"]).first()
    if not existing_video:
        new_video = Video(
            bvid=dyn["bvid"],
            title=dyn.get("title") or "",
            mid=dyn["mid"],
            pub_time=dyn.get("pub_ts"),
            status="pending"
        )
        db.add(new_video)
        logger.info("[视频动态] %s | %s (%s) → 创建 Video 记录", 
                    dyn.get("sub_name", ""), dyn.get("title", ""), dyn["bvid"])
    else:
        logger.debug("[视频动态] %s 已存在，跳过", dyn["bvid"])
```

- [ ] **Step 3: 添加日志头部**

第 117 行 `[检测] 开始检查新动态...` 之后确保有 logger 定义。

- [ ] **Step 4: 写集成测试**

```bash
cat > tests/integration/test_video_dynamic_creation.py << 'EOF'
import pytest
import sys
sys.path.insert(0, '.')
from unittest.mock import patch, MagicMock
from app.modules.dynamic import DynamicFetcher
from app.models.database import get_db, Video, Dynamic
from app.scheduler import check_new_dynamics

def test_video_dynamic_creates_both_records():
    """视频动态应同时创建 Dynamic 和 Video 记录"""
    with patch.object(DynamicFetcher, 'fetch_dynamic') as mock_fetch:
        mock_fetch.return_value = [{
            "dynamic_id": "TEST123",
            "type": "DYNAMIC_TYPE_AV",
            "bvid": "BV1TEST12345",
            "title": "测试视频",
            "text": "",
            "image_urls": [],
            "images": [],
            "pub_ts": 1713000000,
            "mid": "322005137",
            "sub_name": "呆咪"
        }]
        
        # 先清空测试数据
        db = get_db()
        db.query(Video).filter_by(bvid="BV1TEST12345").delete()
        db.query(Dynamic).filter_by(dynamic_id="TEST123").delete()
        db.commit()
        
        check_new_dynamics()
        
        # 验证 Video 创建
        video = db.query(Video).filter_by(bvid="BV1TEST12345").first()
        assert video is not None, "Video 记录未创建"
        assert video.title == "测试视频"
        
        # 验证 Dynamic 创建且 video_bvid 填充
        dynamic = db.query(Dynamic).filter_by(dynamic_id="TEST123").first()
        assert dynamic is not None, "Dynamic 记录未创建"
        assert dynamic.video_bvid == "BV1TEST12345"
        
        db.close()
EOF
```

- [ ] **Step 5: 运行测试**

```bash
uv run pytest tests/integration/test_video_dynamic_creation.py -v
```

预期: PASS

- [ ] **Step 6: 提交**

```bash
git add app/scheduler.py tests/integration/test_video_dynamic_creation.py
git commit -m "feat: create Video record when video dynamic detected"
```

---

## Task 4: 移除 check_new_videos 调度

**文件:** `app/scheduler.py:202-240`

**目标:** 删除 `check_new_videos` 函数及其调度注册。

- [ ] **Step 1: 查看 start_scheduler 函数**

第 202-225 行，确认 `schedule.every(video_interval).minutes.do(check_new_videos)` 位置。

- [ ] **Step 2: 删除 check_new_videos 函数（第 60-113 行）**

删除整个 `check_new_videos` 函数。

- [ ] **Step 3: 删除调度注册（第 210-215 行）**

删除:
```python
# 视频检测
if video_interval > 0:
    logger.info("视频检测频率: 每%d分钟", video_interval)
    schedule.every(video_interval).minutes.do(check_new_videos)
else:
    logger.info("视频检测: 已禁用 (VIDEO_CHECK_INTERVAL=%d)", video_interval)
```

- [ ] **Step 4: 移除 check_new_videos 的 import（第 8 行）**

如果第 8 行 `from app.modules.bilibili import fetch_channel_videos` 不再被使用，移除。

- [ ] **Step 5: 验证程序仍能启动**

```bash
uv run python -c "
from app.scheduler import start_scheduler
print('scheduler loaded OK')
"
```

预期: 无错误输出

- [ ] **Step 6: 提交**

```bash
git add app/scheduler.py
git commit -m "feat: remove check_new_videos, use dynamics for all content detection"
```

---

## Task 5: 更新 TODO.md

- [ ] **Step 1: 标记已完成**

```bash
# TODO.md 第 1 行
# 原来: * [ ] 动态监测中已有视频内容, 不需要单独的视频监测
# 改为:
* [x] 动态监测中已有视频内容, 不需要单独的视频监测 ✓
```

---

## 验证步骤

所有改动完成后，运行完整测试：

```bash
uv run pytest tests/ -v
```

确认所有测试通过，特别是：
- `tests/unit/test_dynamic_parser.py` — bvid 提取
- `tests/integration/test_video_dynamic_creation.py` — Video + Dynamic 同时创建

手动验证（如果有新动态）：
```bash
uv run python -c "
from app.scheduler import check_new_dynamics
check_new_dynamics()
"
```
观察日志中是否出现 `[视频动态]` 开头的记录。

---

## 改动文件清单

| 文件 | 改动类型 |
|------|----------|
| `app/models/database.py` | 修改 — 新增 video_bvid 字段 |
| `app/modules/dynamic.py` | 修改 — _parse_dynamic 提取 bvid |
| `app/scheduler.py` | 修改 — 创建 Video 记录 + 移除 check_new_videos |
| `tests/unit/test_dynamic_parser.py` | 新增 |
| `tests/integration/test_video_dynamic_creation.py` | 新增 |
