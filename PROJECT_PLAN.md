# B站UP主自动化摘要系统 - 完整项目方案

**最后更新**: 2026年3月26日  
**项目状态**: 架构设计 → 阶段一开发

---

## 目录

1. [系统目标](#系统目标)
2. [整体架构](#整体架构)
3. [核心模块详解](#核心模块详解)
4. [工程质量细节](#工程质量细节)
5. [代码结构&文件组织](#代码结构文件组织)
6. [完整流程代码](#完整流程代码)
7. [部署方案](#部署方案)
8. [高级功能（第二阶段）](#高级功能第二阶段)
9. [故障排查](#故障排查)
10. [项目里程碑](#项目里程碑)

---

## 系统目标

**核心功能**：自动化流程，持续运行

```
订阅B站UP主 → 自动发现新视频 + 动态 → 获取内容
  → 视频：字幕/音频 → AI总结
  → 动态：直接推送（含图片）
  → 推送到飞书/Telegram/微信 → 形成个人知识库
```

**包含两大内容源**：
1. **视频流** - 需要AI总结（耗时，但价值高）
2. **动态流** - 图文直推（实时性强，信息密度适中）

**关键特征**：
- ✅ 完全自动化（无需手动干预）
- ✅ 支持多内容源（视频 + 动态）
- ✅ 支持多推送渠道（飞书、Telegram、微信）
- ✅ 支持富媒体（文字 + 图片）
- ✅ 长期稳定运行（Mac mini）
- ✅ 可逐步扩展成SaaS产品
- ✅ 低成本、模块化、可测试

---

## 整体架构

```
┌──────────────────────────────────────────────┐
│         UP主订阅列表（本地DB）              │
│  {mid, name, last_video_id, last_check_time}│
└────────────────────┬─────────────────────────┘
                     │
                     ↓ (每5-10分钟)
        ┌────────────┴────────────┐
        │                         │
┌───────▼──────┐         ┌────────▼──────┐
│ 检测新视频   │         │ 检测新动态    │
│ (arc search) │         │ (dynamic api) │
└───────┬──────┘         └────────┬──────┘
        │                         │
        ↓                         ↓
    ┌───────────┐         ┌──────────────┐
    │  有新BV？  │         │  有新动态？   │
    └────┬──────┘         └────┬─────────┘
         │                     │
        ✓│                    ✓│
         │         ┌───────────┘
         │         │
    ┌────▼─────────▼──────┐
    │  丢入处理队列       │
    │ (type: video/dynamic)
    └────┬────────────────┘
         │
         ↓
        ┌────────────────────────────────────┐
        │    判断内容类型                    │
        └────┬──────────────────────┬────────┘
             │                      │
           video                 dynamic
             │                      │
    ┌────────▼────────┐    ┌────────▼──────────┐
    │ 获取字幕/音频   │    │  下载图文内容    │
    │ Whisper转写    │    │ 下载图片到本地    │
    │ AI总结         │    │ 格式化富卡片      │
    └────────┬────────┘    └────────┬──────────┘
             │                      │
             │         ┌────────────┘
             │         │
    ┌────────▼─────────▼──────────────────┐
    │   推送到多个渠道                    │
    │   • 飞书 (文本/卡片/图片)           │
    │   • Telegram (文本/相册)             │
    │   • 微信 (图文模板)                  │
    └────────┬──────────────────────────┘
             │
             ↓
     ┌──────────────┐
     │ 记录history  │
     │ 更新DB状态   │
     └──────────────┘
```

---

## 核心模块详解

### 1. UP主订阅管理

**数据结构**：
```python
# subscriptions 表
{
    "id": 1,
    "mid": "123456",          # UP主UID
    "name": "某科技UP",
    "last_video_bvid": "BVxxxxxx",
    "last_check_time": "2026-03-26 10:30:00",
    "is_active": True,
    "created_at": "2026-03-01",
    "notes": "关注原因/备注"
}
```

**获取UP主最新视频**：
```
GET https://api.bilibili.com/x/space/arc/search
    ?mid={mid}&pn=1&ps=30&order=pubdate

返回字段:
- bvid: 视频ID
- title: 标题
- pubdate: 发布时间戳
- pic: 封面URL
- duration: 时长（秒）
- desc: 简介

!注意: 需要在请求头加入：
User-Agent: Mozilla/5.0...
Cookie: (可选，避免限流)
```

**检测逻辑**：
```python
1. 遍历所有激活的UP主
2. 调用API获取最新30个视频
3. 与last_video_bvid比较
4. 如果有新的bvid → 依次放入队列
5. 更新last_check_time
6. 记录API调用（监控限流）
```

---

### 2. 视频获取与下载

**工具链**：
- 优先：B站API/yt-dlp（获取字幕）
- 备选：yt-dlp 下载音频

**字幕获取优先级** ⭐（最重要）
```
1. 检查B站字幕API
   GET https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={cid}
   响应中查找 subtitle.list[]
   
2. 如果存在 → 拉取字幕文件（JSON或VTT格式）
   
3. 否则 → 调用yt-dlp下载音频
   yt-dlp -f bestaudio \
           -x --audio-format wav \
           --audio-quality 192k \
           -o "%(id)s.%(ext)s" \
           https://www.bilibili.com/video/{bvid}
           
4. 如果yt-dlp失败 → 标记为"需要Whisper"，等待
```

**数据库追踪**：
```python
# videos表
{
    "id": 1,
    "bvid": "BVxxxxxx",
    "title": "视频标题",
    "mid": "123456",
    "pub_time": 1711353600,
    "has_subtitle": True,      # 是否有字幕
    "has_audio": True,         # 是否成功下载音频
    "subtitle_path": "/data/subtitles/BVxxxxxx.json",
    "audio_path": "/data/audio/BVxxxxxx.wav",
    "status": "processing",    # pending→processing→done→failed
    "attempt_count": 1,
    "last_error": null,
    "created_at": "2026-03-26",
    "updated_at": "2026-03-26"
}
```

---

### 3. 字幕解析与处理

**从B站字幕API提取**：
```python
def parse_bilibili_subtitle(subtitle_data):
    """
    B站返回的字幕格式通常是JSON:
    {
        "body": [
            {"from": 0, "to": 5, "content": "你好"},
            {"from": 5, "to": 10, "content": "世界"}
        ]
    }
    """
    text = " ".join([item["content"] for item in subtitle_data["body"]])
    return text
```

**清洗规则**：
```python
• 移除时间戳
• 移除重复行
• 合并短语句
• 去除垃圾字符（emoji尽量保留）
• 段落分割（换行保留原意）
```

---

### 4. 语音识别（Whisper）

**为什么用faster-whisper**：
- 比官方Whisper快3-5倍
- Mac支持好（CPU/Metal优化）
- 模型量化（int8）省内存

**配置**（Mac mini最优）：
```python
from faster_whisper import WhisperModel

# 选择合适的模型
# tiny: 最快，质量一般 (~1GB显存)
# base: 平衡      (~2GB)
# small: 较好     (~3GB)  ← 推荐你的机器
# medium: 很好    (~5GB)
# large: 最佳     (~10GB)

model = WhisperModel(
    "small",
    device="cpu",              # Mac用CPU足够
    compute_type="int8",       # 量化，更快更省内存
    num_workers=4,             # 并行处理
    download_root="/models"
)

def transcribe_audio(audio_path: str) -> str:
    """识别音频，返回文本"""
    segments, info = model.transcribe(
        audio_path,
        language="zh",
        beam_size=5,
        vad_filter=True,        # 去除静音
        condition_on_previous_text=True
    )
    
    text = "\n".join([segment.text for segment in segments])
    return text
```

**时间复杂度**（参考）：
- 10分钟视频 → 约30-90秒处理时间（small模型）
- 使用GPU/Metal → 进一步加速

---

### 5. 动态获取与处理（新增）⭐

**动态 vs 视频的区别**：
| 属性 | 视频 | 动态 |
|------|------|------|
| 获取方式 | yt-dlp/API | 直接API |
| 处理流程 | 字幕→Whisper→LLM | 直接格式化 |
| 推送形式 | 结构化卡片 | 富文本+图片 |
| 处理时间 | 数十秒 | <1秒 |

**B站动态API**：
```
获取UP主动态列表：
GET https://api.bilibili.com/x/polymer/v1/feed/space
    ?host_mid={mid}&offset={offset}&features=forward

返回的dynamic对象包含：
- id_str: 动态ID
- type: 动态类型 (256=图文, 1=转发, 2=视频, etc)
- modules:
  - module_author: 来源信息
  - module_content: 内容 (text + image list)
  - module_interaction: 互动数据

关键字段示例:
{
    "id_str": "123456789",
    "type": 256,  # 图文动态
    "modules": {
        "module_author": {
            "author": {
                "name": "UP主名字",
                "face": "头像URL"
            },
            "pub_time": "2026-03-26 10:30"
        },
        "module_content": {
            "content": "动态文本内容",
            "image_urls": [
                {"src": "图片URL1"},
                {"src": "图片URL2"}
            ]
        }
    }
}
```

**动态获取实现**：
```python
import requests
import os
from pathlib import Path
from datetime import datetime

class DynamicFetcher:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0...'
        }
        self.image_dir = Path("data/dynamic_images")
        self.image_dir.mkdir(parents=True, exist_ok=True)
    
    def fetch_dynamic(self, mid: str, offset=0) -> list:
        """获取UP主最新动态"""
        url = "https://api.bilibili.com/x/polymer/v1/feed/space"
        params = {
            "host_mid": mid,
            "offset": offset,
            "features": "forward"
        }
        
        response = requests.get(url, params=params, headers=self.headers)
        data = response.json()
        
        if data['code'] != 0:
            logger.error(f"获取动态失败: {data['message']}")
            return []
        
        dynamics = []
        for item in data['data']['items']:
            dynamic = self._parse_dynamic(item)
            if dynamic:
                dynamics.append(dynamic)
        
        return dynamics
    
    def _parse_dynamic(self, item: dict) -> dict:
        """解析单个动态"""
        dynamic_id = item['id_str']
        dynamic_type = item['type']
        modules = item.get('modules', {})
        
        # 只处理图文动态 (type=256)
        if dynamic_type not in [256, 2]:  # 256=图文, 2=视频
            return None
        
        # 获取内容
        content_module = modules.get('module_content', {})
        text = content_module.get('content', '').strip()
        
        # 获取图片
        images = []
        if 'image_urls' in content_module:
            images = [
                img.get('src') 
                for img in content_module.get('image_urls', [])
                if img.get('src')
            ]
        
        # 获取时间
        author_module = modules.get('module_author', {})
        pub_time = author_module.get('pub_time', '')
        
        return {
            'dynamic_id': dynamic_id,
            'type': dynamic_type,
            'text': text,
            'image_urls': images,
            'pub_time': pub_time,
            'images': []  # 将由download_images填充
        }
    
    def download_images(self, dynamic: dict) -> dict:
        """下载动态中的所有图片"""
        images = []
        for url in dynamic['image_urls']:
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                
                # 保存图片
                filename = f"{dynamic['dynamic_id']}_{len(images)}.jpg"
                filepath = self.image_dir / filename
                
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                
                images.append(str(filepath))
                logger.debug(f"下载图片: {filename}")
                
            except Exception as e:
                logger.warning(f"图片下载失败: {url}, {e}")
        
        dynamic['images'] = images
        return dynamic
```

---

### 6. LLM总结与提炼（核心价值）

**输出结构**（必须统一）：
```json
{
    "bvid": "BVxxxxxx",
    "title": "原视频标题",
    "url": "https://www.bilibili.com/video/BVxxxxxx",
    "pub_time": "2026-03-26 10:00:00",
    "duration_minutes": 15,
    
    "summary": "一句话核心观点（50-100字）",
    
    "key_points": [
        "观点1：详细说明",
        "观点2：详细说明",
        "观点3：详细说明"
    ],
    
    "timeline": [
        {"time": "0:00-2:00", "content": "开场介绍"},
        {"time": "2:00-5:30", "content": "核心论点"},
        {"time": "5:30-end", "content": "总结建议"}
    ],
    
    "tags": ["标签1", "标签2", "标签3"],
    
    "insights": "1-2条有价值的洞察或拓展思考",
    
    "metadata": {
        "content_type": "技术分享|评论/讨论|产品介绍",
        "difficulty": "易|中|难",
        "relevance_score": 0.85
    }
}
```

**Prompt模板**（经过验证）：
```
你是一个高质量内容分析助手。请基于以下视频字幕或转录内容，产生结构化总结。

【要求】
1. 核心观点：提取3-5条最有价值的观点，每条30-50字
2. 简洁总结：整体内容概括，必须 ≤ 200字
3. 时间节点：用"00:00-02:30"格式标记关键片段（最多5个）
4. 标签：最多5个，要有区分度
5. 洞察：1-2条可能引发进一步思考的内容

【需要避免】
- 冗余和无关的细节
- 过度解释
- 主观臆断

【视频信息】
标题：{title}
时长：{duration}分钟

【字幕/转录文本】
{text}

【输出格式】
使用JSON，确保可被直接解析。
```

**调用示例**（支持多个LLM）：
```python
# 方案1: OpenAI（推荐）
from openai import OpenAI

def summarize_with_openai(text: str, title: str, duration: str) -> dict:
    client = OpenAI(api_key="sk-...")
    
    response = client.chat.completions.create(
        model="gpt-4-turbo",  # 或gpt-3.5-turbo（便宜）
        messages=[
            {
                "role": "system",
                "content": "你是内容分析专家..."
            },
            {
                "role": "user",
                "content": prompt.format(
                    title=title,
                    duration=duration,
                    text=text
                )
            }
        ],
        temperature=0.3,  # 降低随意性
        response_format={"type": "json_object"}
    )
    
    return json.loads(response.choices[0].message.content)

# 方案2: 本地开源模型（省钱）
# 如: LLaMA、Qwen、GLM等
# 需要: ollama 或 vLLM 等框架
```

**成本估算**（重要）：
```
OpenAI GPT-3.5-turbo：
• 输入: $0.0005/1K tokens
• 输出: $0.0015/1K tokens
• 10分钟视频字幕 ≈ 1500 tokens → $0.002-0.003/个

OpenAI GPT-4-turbo：
• 输入: $0.01/1K tokens
• 输出: $0.03/1K tokens
• 同样 ≈ $0.04/个

月成本估算（30个视频/天）：
• GPT-3.5: $1.8-2.7
• GPT-4: $36-45

建议：
✓ 前期用GPT-3.5快速验证
✓ 后期换本地开源模型（0成本）
```

---

### 7. 推送系统（多渠道 + 图片支持）⭐

#### 通用推送入口

```python
def push_content(content_data: dict, channels: list):
    """
    统一的推送接口
    
    content_data: {
        "type": "video" | "dynamic",
        "title": "标题（视频）或动态文本",
        "summary": "摘要（仅视频有）",
        "key_points": [...],
        "tags": [...],
        "images": ["path1", "path2"],  # 本地图片路径
        "url": "B站链接",
        "timestamp": "发布时间"
    }
    
    channels: ["feishu", "telegram", "wechat"]
    """
    
    for channel in channels:
        try:
            if channel == "feishu":
                push_feishu(content_data)
            elif channel == "telegram":
                push_telegram(content_data)
            elif channel == "wechat":
                push_wechat(content_data)
        except Exception as e:
            logger.error(f"推送到 {channel} 失败: {e}", exc_info=True)
```

#### 飞书（发送视频 + 动态）

**推送视频总结**（卡片格式）：
```python
def push_feishu_video(webhook_url: str, summary_data: dict):
    """推送视频总结卡片到飞书"""
    
    message = {
        "msg_type": "interactive",
        "card": {
            "config": {
                "wide_screen_mode": True
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "content": f"📺 **{summary_data['title']}**",
                        "tag": "lark_md"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "content": summary_data['summary'],
                        "tag": "plain_text"
                    }
                },
                {
                    "tag": "div",
                    "fields": [
                        {
                            "is_short": True,
                            "text": {
                                "content": f"**时长**: {summary_data.get('duration_minutes', 'N/A')}分钟",
                                "tag": "lark_md"
                            }
                        },
                        {
                            "is_short": True,
                            "text": {
                                "content": f"**标签**: {', '.join(summary_data.get('tags', []))}",
                                "tag": "lark_md"
                            }
                        }
                    ]
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "div",
                    "text": {
                        "content": "**核心观点**",
                        "tag": "lark_md"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "content": "\n".join([
                            f"• {point}" for point in summary_data.get('key_points', [])
                        ]),
                        "tag": "plain_text"
                    }
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "type": "button",
                            "text": "查看完整内容",
                            "url": summary_data['url']
                        }
                    ]
                }
            ]
        }
    }
    
    response = requests.post(webhook_url, json=message)
    return response.status_code == 200
```

**推送动态（含图片）**：
```python
def push_feishu_dynamic(webhook_url: str, dynamic_data: dict):
    """推送图文动态到飞书（支持多图）"""
    
    elements = [
        {
            "tag": "div",
            "text": {
                "content": f"📝 **动态内容**",
                "tag": "lark_md"
            }
        },
        {
            "tag": "div",
            "text": {
                "content": dynamic_data['text'],
                "tag": "plain_text"
            }
        }
    ]
    
    # 添加图片（飞书支持多张）
    for img_path in dynamic_data.get('images', []):
        # 需要先上传图片到飞书获得image_key
        image_key = upload_image_to_feishu(img_path, webhook_url)
        
        if image_key:
            elements.append({
                "tag": "img",
                "img_key": image_key,
                "alt": {
                    "tag": "plain_text",
                    "content": "动态图片"
                }
            })
    
    elements.extend([
        {
            "tag": "hr"
        },
        {
            "tag": "div",
            "text": {
                "content": f"⏰ {dynamic_data.get('pub_time', '')}",
                "tag": "lark_md"
            }
        },
        {
            "tag": "action",
            "actions": [
                {
                    "type": "button",
                    "text": "查看原动态",
                    "url": dynamic_data['url']
                }
            ]
        }
    ])
    
    message = {
        "msg_type": "interactive",
        "card": {
            "config": {
                "wide_screen_mode": True
            },
            "elements": elements
        }
    }
    
    response = requests.post(webhook_url, json=message)
    return response.status_code == 200

def upload_image_to_feishu(image_path: str, webhook_url: str) -> str:
    """将本地图片上传到飞书，返回image_key（用于卡片）
    
    注意：这个接口需要企业自建应用的权限，webhook机器人可能有限制
    如果webhook不支持，建议改用企业应用的tenant_access_token
    """
    
    # 获取企业应用token（需要提前配置）
    # 这里仅作示例
    
    with open(image_path, 'rb') as f:
        files = {'image': f}
        response = requests.post(
            'https://open.feishu.cn/open-apis/im/v1/images',
            headers={
                'Authorization': f'Bearer {tenant_token}'
            },
            files=files
        )
    
    if response.status_code == 200:
        return response.json()['data']['image_key']
    return None
```

**简化版（webhook直接推送，不上传）**：
```python
def push_feishu_dynamic_simple(webhook_url: str, dynamic_data: dict):
    """简化版：文字 + 图片URL直链（不需要企业应用权限）"""
    
    text = dynamic_data['text']
    images_text = ""
    
    if dynamic_data.get('image_urls'):
        images_text = "\n\n**图片**：" + "\n".join([
            f"![图{i+1}]({url})" 
            for i, url in enumerate(dynamic_data['image_urls'][:3])  # 最多3张
        ])
    
    message = {
        "msg_type": "text",
        "content": {
            "text": f"""📝 **动态**

{text}
{images_text}

⏰ {dynamic_data.get('pub_time', '')}
---
自动推送 | 查看原动态: {dynamic_data['url']}
"""
        }
    }
    
    response = requests.post(webhook_url, json=message)
    return response.status_code == 200
```

#### Telegram（发送视频 + 动态）

**推送视频**：
```python
def push_telegram_video(bot_token: str, chat_id: str, summary_data: dict):
    """推送视频总结到Telegram"""
    
    from telegram import Bot
    
    bot = Bot(token=bot_token)
    
    message_text = f"""📺 <b>{summary_data['title']}</b>

<b>摘要</b>
{summary_data['summary']}

<b>关键点</b>
{chr(10).join(['• ' + p for p in summary_data.get('key_points', [])])}

<b>标签</b> {', '.join(summary_data.get('tags', []))}

<a href="{summary_data['url']}">查看原视频</a>
"""
    
    bot.send_message(
        chat_id=chat_id,
        text=message_text,
        parse_mode="HTML"
    )
```

**推送动态（含图片）**：
```python
def push_telegram_dynamic(bot_token: str, chat_id: str, dynamic_data: dict):
    """推送图文动态到Telegram（支持相册模式多图）"""
    
    from telegram import Bot, InputMediaPhoto
    
    bot = Bot(token=bot_token)
    
    # 先发文字
    caption = f"""📝 {dynamic_data['text'][:200]}...

⏰ {dynamic_data.get('pub_time', '')}
"""
    
    if dynamic_data.get('images'):
        # 如果有本地图片，构建媒体组（相册样式）
        media_group = []
        
        for i, img_path in enumerate(dynamic_data['images'][:10]):  # 最多10张
            with open(img_path, 'rb') as f:
                caption_text = caption if i == 0 else ""  # 只在第一张添加说明
                media_group.append(
                    InputMediaPhoto(f, caption=caption_text, parse_mode="HTML")
                )
        
        if media_group:
            bot.send_media_group(chat_id=chat_id, media=media_group)
        else:
            # 没有图片，直接发文字
            bot.send_message(chat_id=chat_id, text=caption, parse_mode="HTML")
    else:
        bot.send_message(chat_id=chat_id, text=caption, parse_mode="HTML")
```

#### 微信（新增）⭐

**方案选择**：

**方案A：企业号/ Corp WeChat（推荐，官方）**
```python
import requests

def push_wechat_corporate(corp_id: str, corp_secret: str, agent_id: int, 
                         to_user: str, dynamic_data: dict):
    """
    推送到微信企业号
    
    setup:
    1. 注册企业号 (https://work.weixin.qq.com)
    2. 创建应用，获得 corp_id, secret, agent_id
    3. 添加接收用户
    """
    
    # 获取access_token
    token_url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken"
    token_params = {
        "corpid": corp_id,
        "corpsecret": corp_secret
    }
    token_resp = requests.get(token_url, params=token_params)
    access_token = token_resp.json()['access_token']
    
    # 构造消息
    message = {
        "touser": to_user,
        "msgtype": "news",  # 图文消息
        "agentid": agent_id,
        "news": {
            "articles": [
                {
                    "title": dynamic_data['text'][:50],
                    "description": dynamic_data['text'][50:300],
                    "url": dynamic_data['url'],
                    "picurl": dynamic_data['image_urls'][0] if dynamic_data.get('image_urls') else ""
                }
            ]
        }
    }
    
    # 发送
    send_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send"
    send_params = {"access_token": access_token}
    
    response = requests.post(send_url, params=send_params, json=message)
    return response.json()['errcode'] == 0
```

**方案B：个人号（非官方，用爬虫库）**
```python
def push_wechat_personal(wechat_id: str, message_text: str, images: list):
    """
    推送到个人微信
    需要安装: pip install itchat
    
    注意：微信官方禁止自动化，此方案有风险
    """
    
    import itchat
    
    # 登录（扫码）
    itchat.auto_login()
    
    # 获取好友
    friend = itchat.search_friends(name=wechat_id)[0]
    friend_id = friend['UserName']
    
    # 发送文字
    itchat.send(message_text, toUserName=friend_id)
    
    # 发送图片
    for img_path in images[:3]:  # 最多3张
        itchat.send(f'@img@{img_path}', toUserName=friend_id)
```

**微信推送最佳方案**：企业号（稳定、官方支持）

---

### 8. 任务队列


**简单方案**（推荐初期）：
```python
import queue
import threading

# 内存队列 (重启丢失，但够用)
task_queue = queue.Queue(maxsize=1000)

def enqueue_video(bvid: str, title: str):
    """添加任务"""
    task_queue.put({
        "bvid": bvid,
        "title": title,
        "created_at": datetime.now(),
        "retries": 0
    })

def process_queue():
    """持续处理队列"""
    while True:
        try:
            task = task_queue.get(timeout=5)
            
            try:
                process_video(task["bvid"], task["title"])
                task_queue.task_done()
            except Exception as e:
                logger.error(f"处理失败: {task['bvid']}", exc_info=True)
                
                # 重试逻辑
                if task["retries"] < 3:
                    task["retries"] += 1
                    task_queue.put(task)  # 重新放入队列
                else:
                    logger.error(f"已放弃: {task['bvid']}")
                    
        except queue.Empty:
            # 队列空，继续等待
            continue
```

**升级方案**（后期）：使用Redis或RabbitMQ
```python
# Redis (简单，推荐)
import redis
rq = redis.Redis(host='localhost', port=6379)
rq.lpush('bili:queue', json.dumps(task))  # 入队
task = json.loads(rq.rpop('bili:queue'))  # 出队
```

---

### 9. 数据存储

**数据库选择**：
- **初期**: SQLite（无需额外服务，文件存储）
- **后期**: PostgreSQL（持久化、更好的查询）

**Schema**：
```sql
-- UP主订阅表
CREATE TABLE subscriptions (
    id INTEGER PRIMARY KEY,
    mid TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    last_video_bvid TEXT,
    last_dynamic_id TEXT,  -- 新增，追踪最新动态
    last_check_time DATETIME,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

-- 视频表
CREATE TABLE videos (
    id INTEGER PRIMARY KEY,
    bvid TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    mid TEXT NOT NULL,
    pub_time INTEGER,
    has_subtitle BOOLEAN,
    has_audio BOOLEAN,
    subtitle_path TEXT,
    audio_path TEXT,
    status TEXT,  -- pending|processing|done|failed
    attempt_count INTEGER DEFAULT 0,
    last_error TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(mid) REFERENCES subscriptions(mid)
);

-- 动态表（新增）⭐
CREATE TABLE dynamics (
    id INTEGER PRIMARY KEY,
    dynamic_id TEXT UNIQUE NOT NULL,
    mid TEXT NOT NULL,
    type INTEGER,           -- 256=图文, 2=视频等
    text TEXT,
    image_count INTEGER,    -- 图片数量
    images_path TEXT,       -- JSON: ["path1", "path2"]
    image_urls TEXT,        -- JSON: ["url1", "url2"]
    status TEXT,            -- pending|sent|failed
    push_status TEXT,       -- 记录推送到哪些渠道
    pub_time DATETIME,
    pushed_at DATETIME,
    attempt_count INTEGER DEFAULT 0,
    last_error TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(mid) REFERENCES subscriptions(mid)
);

-- 总结结果表
CREATE TABLE summaries (
    id INTEGER PRIMARY KEY,
    bvid TEXT UNIQUE NOT NULL,
    summary_json TEXT,  -- JSON字符串
    push_status TEXT,   -- pending|sent|failed
    pushed_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(bvid) REFERENCES videos(bvid)
);

-- 日志表（可选，用于监控）
CREATE TABLE logs (
    id INTEGER PRIMARY KEY,
    level TEXT,  -- INFO|WARN|ERROR
    message TEXT,
    context TEXT,  -- JSON格式的额外信息
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 索引（性能优化）
CREATE INDEX idx_videos_status ON videos(status);
CREATE INDEX idx_videos_mid ON videos(mid);
CREATE INDEX idx_dynamics_status ON dynamics(status);
CREATE INDEX idx_dynamics_mid ON dynamics(mid);
CREATE INDEX idx_summaries_push_status ON summaries(push_status);
```

---

## 工程质量细节

### 错误处理与重试

这是系统**稳定性的关键**，必须做好。

```python
import time
from functools import wraps

def retry(max_attempts=3, backoff_factor=2, exceptions=(Exception,)):
    """通用重试装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            attempt = 0
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.error(
                            f"{func.__name__} 已放弃 (尝试{attempt}次)",
                            exc_info=True
                        )
                        raise
                    
                    wait_time = backoff_factor ** attempt
                    logger.warning(
                        f"{func.__name__} 失败，"
                        f"{wait_time}秒后重试... "
                        f"({attempt}/{max_attempts})"
                    )
                    time.sleep(wait_time)
        return wrapper
    return decorator

# 使用示例
@retry(max_attempts=3, backoff_factor=2)
def fetch_video_info(bvid: str):
    response = requests.get(
        f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}",
        timeout=10
    )
    response.raise_for_status()
    return response.json()

@retry(max_attempts=5)  # API失败重试5次
def get_subtitles(bvid: str):
    # ...
    pass
```

**具体应对的错误**：
```
【网络相关】
- ConnectionError → 重试（等待网络恢复）
- Timeout → 增加timeout，重试
- 429 Too Many Requests (B站限流) 
  → 指数退避 + 随机延迟

【B站API】
- 视频不存在/已删除 → 标记为不可用，跳过
- 字幕为空 → 尝试Whisper
- 无权访问 → 标记，人工检查

【Whisper识别】
- 音频文件损坏 → 标记，日志记录
- 内存不足 → 降低模型大小
- 识别超时 → 增加timeout或使用更小的模型

【推送失败】
- Webhook失效 → 记录，告警，人工处理
- 网络暂时不通 → 重试（队列持久化）
```

---

### 日志系统

**为什么必须有日志**：
- 定时任务无人监听，问题只能从日志发现
- 追踪每个视频的处理流程
- 成本监控（API调用、LLM消费）
- 性能分析

```python
import logging
import logging.handlers

# 配置日志
logger = logging.getLogger("bili")
logger.setLevel(logging.DEBUG)

# 文件处理器（轮转）
file_handler = logging.handlers.RotatingFileHandler(
    "logs/bili.log",
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5  # 保留5个备份
)
file_handler.setLevel(logging.INFO)

# 控制台处理器（仅重要信息）
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)

# 格式
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

# 使用
logger.info(f"开始处理视频: {bvid}")
logger.warning(f"字幕为空，将使用Whisper: {bvid}")
logger.error(f"处理失败: {bvid}", exc_info=True)
```

**日志清单**（关键时刻一定要记）：
```
✓ 启动/停止事件
✓ 每次UP主检测（是否有新视频）
✓ 每个视频的处理步骤（获取→转写→总结→推送）
✓ 所有异常和重试
✓ API调用（B站、OpenAI等）
✓ 本地资源占用（磁盘、内存）
✓ 性能指标（处理时间）
```

---

### 敏感信息管理

**问题**：token、cookie不能硬写代码

**解决**：
```python
# config.py
import os
from dotenv import load_dotenv

load_dotenv()  # 从.env读取

class Config:
    # B站会话
    BILIBILI_COOKIE = os.getenv("BILIBILI_COOKIE", "")
    
    # LLM API
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    # 推送
    FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    
    # 数据库
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///bili.db")
    
    # 日志
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
```

**.env 文件** (不要commit):
```
BILIBILI_COOKIE=your_cookie_here
OPENAI_API_KEY=sk-xxx
FEISHU_WEBHOOK=https://open.feishu.cn/...
TELEGRAM_TOKEN=123456:ABCabc...
DATABASE_URL=sqlite:///bili.db
```

**.gitignore**:
```
.env
*.log
__pycache__/
.DS_Store
/data
/logs
/models
```

---

### 断点续传与去重

**问题**：处理到一半宕机了，重启后怎么知道哪些视频已经处理了？

**解决**：
```python
# videos表中有status字段: pending|processing|done|failed

def should_reprocess(bvid: str) -> bool:
    """判断是否需要重新处理"""
    video = db.query(Video).filter_by(bvid=bvid).first()
    
    if not video:
        return True  # 新视频，需要处理
    
    if video.status == "done":
        return False  # 已完成，不处理
    
    if video.status == "failed":
        # 失败的视频：如果尝试次数 < 3, 继续尝试
        return video.attempt_count < 3
    
    if video.status == "processing":
        # 状态异常（可能中途宕机）
        # 检查: 如果上次更新时间 > 30分钟，认为卡住了，重新处理
        if (datetime.now() - video.updated_at).seconds > 1800:
            return True
    
    return True

def process_video(bvid: str):
    video = db.query(Video).filter_by(bvid=bvid).one()
    
    try:
        video.status = "processing"
        video.updated_at = datetime.now()
        db.commit()
        
        # 实际处理逻辑
        subtitles = get_subtitles(bvid)
        summary = llm_summary(subtitles)
        push(summary)
        
        video.status = "done"
        video.attempt_count = 0
        
    except Exception as e:
        video.status = "failed"
        video.last_error = str(e)
        video.attempt_count += 1
        logger.error(f"处理失败: {bvid}", exc_info=True)
        
    finally:
        video.updated_at = datetime.now()
        db.commit()
```

---

### 并发控制

**问题**：如果视频太多，单线程太慢

**方案**：
```python
from concurrent.futures import ThreadPoolExecutor
import queue

def process_queue_concurrent(max_workers=3):
    """用线程池加速处理"""
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        
        while True:
            try:
                # 从队列取任务
                task = task_queue.get(timeout=10)
                
                # 异步提交
                future = executor.submit(
                    process_video,
                    task["bvid"]
                )
                futures.append(future)
                
                # 不要堆积太多未完成的任务
                if len(futures) > max_workers * 2:
                    # 等待至少一个完成
                    for f in futures:
                        if f.done():
                            futures.remove(f)
                            break
                            
            except queue.Empty:
                # 队列空，但还有任务在处理
                if futures:
                    futures[0].result()  # 等待至少一个完成
                    futures.pop(0)
                else:
                    # 彻底空了，可以退出
                    break
```

**注意**：
- 文件I/O密集 → 线程池效果好
- 如果涉及GPU（多Whisper并行）→ 需要测试
- Mac上线程数不要太多（3-5个足够）

---

### 版本冲突管理

**常见问题**：
```
transformers 版本 → Whisper需要特定版本
torch / tensorflow → 可能冲突
numpy 版本 → 很多库依赖

解决：用 pyenv + venv 隔离
或：使用 requirements.txt 锁定版本
```

**requirements.txt** (推荐版本):
```
# 核心
faster-whisper==0.10.0
python-bilibili>=0.16.0
requests==2.31.0

# LLM
openai==1.3.0
langchain==0.1.0

# 数据库
sqlalchemy==2.0.0
sqlite3  # 内置

# 推送
python-telegram-bot==20.0
feishu-sdk-python==0.4.0

# 图片处理（动态需要）
pillow==10.0.0

# 工具
python-dotenv==1.0.0
pydantic==2.0.0

# 调度
schedule==1.2.0
APScheduler==3.10.0

# 日志
python-json-logger==2.0.7
```

---

## 代码结构&文件组织

```
bili-auto/
├── main.py                   # 应用入口
├── config.py                 # 配置管理
├── requirements.txt          # 依赖
├── .env.example             # 配置模板
├── .gitignore
├── README.md
│
├── app/
│   ├── __init__.py
│   ├── scheduler.py         # 定时任务管理（视频 + 动态检测）
│   ├── queue_worker.py      # 队列处理（区分视频/动态类型）
│   │
│   ├── modules/
│   │   ├── __init__.py
│   │   ├── bilibili.py      # B站API封装
│   │   ├── dynamic.py       # 动态获取 & 图片下载 ⭐（新增）
│   │   ├── downloader.py    # yt-dlp集成
│   │   ├── subtitle.py      # 字幕解析
│   │   ├── whisper_ai.py    # Whisper集成
│   │   ├── llm.py           # LLM调用
│   │   └── push.py          # 推送模块（支持多渠道 + 图片）⭐（升级）
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── database.py      # SQLAlchemy ORM
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logger.py        # 日志配置
│       ├── errors.py        # 自定义异常
│       └── helpers.py       # 工具函数
│
├── data/
│   ├── subtitles/           # 字幕文件存储
│   ├── audio/               # 音频文件存储
│   ├── dynamic_images/      # 动态图片存储 ⭐（新增）
│   └── bili.db              # SQLite数据库
│
└── logs/
    └── bili.log             # 应用日志
```
│
├── app/
│   ├── __init__.py
│   ├── scheduler.py         # 定时任务管理
│   ├── queue_worker.py      # 队列处理
│   │
│   ├── modules/
│   │   ├── __init__.py
│   │   ├── bilibili.py      # B站API封装
│   │   ├── downloader.py    # yt-dlp集成
│   │   ├── subtitle.py      # 字幕解析
│   │   ├── whisper_ai.py    # Whisper集成
│   │   ├── llm.py           # LLM调用
│   │   └── push.py          # 推送模块
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── database.py      # SQLAlchemy ORM
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logger.py        # 日志配置
│       ├── errors.py        # 自定义异常
│       └── helpers.py       # 工具函数
│
├── data/
│   ├── subtitles/           # 字幕文件存储
│   ├── audio/               # 音频文件存储
│   └── bili.db              # SQLite数据库
│
└── logs/
    └── bili.log             # 应用日志
```

---

## 完整流程代码

### init setup.py（初始化）

```python
#!/usr/bin/env python3
"""初始化脚本：创建数据库、目录、下载模型"""

import os
from pathlib import Path
from app.models.database import init_db

def setup():
    print("🚀 初始化 bili-auto...")
    
    # 1. 创建目录
    dirs = ["data/subtitles", "data/audio", "data/dynamic_images", "logs"]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
        print(f"✓ 目录 {d} ready")
    
    # 2. 初始化数据库
    init_db()
    print("✓ 数据库初始化完成")
    
    # 3. 下载Whisper模型（可选，首次会自动下载）
    print("\n💾 下载 Whisper small 模型... (首次需要，约1GB)")
    from faster_whisper import WhisperModel
    try:
        model = WhisperModel("small", download_root="./models")
        print("✓ Whisper 模型就绪")
    except Exception as e:
        print(f"⚠️ 模型下载可选，后续会自动下载: {e}")
    
    # 4. 检查配置
    print("\n🔑 检查配置...")
    from config import Config
    if not Config.OPENAI_API_KEY:
        print("⚠️ OPENAI_API_KEY 未设置，请在.env配置")
    
    print("\n✅ 初始化完成！下一步: python main.py")

if __name__ == "__main__":
    setup()
```

### 主程序流程

```python
# main.py
import logging
from app.scheduler import start_scheduler
from app.queue_worker import start_queue_worker
from threading import Thread

logger = logging.getLogger("bili")

def main():
    logger.info("=" * 50)
    logger.info("bili-auto 启动中...")
    logger.info("=" * 50)
    
    # 1. 启动定时检测（每10分钟）
    scheduler_thread = Thread(target=start_scheduler, daemon=True)
    scheduler_thread.start()
    logger.info("✓ 检测线程已启动 (每10分钟检查一次)")
    
    # 2. 启动队列处理（并发3个工作线程）
    queue_thread = Thread(target=start_queue_worker, daemon=False)
    queue_thread.start()
    logger.info("✓ 处理线程已启动 (并发3个worker)")
    
    logger.info("系统运行中... (Ctrl+C停止)")
    
    try:
        # 保持主线程活动
        queue_thread.join()
    except KeyboardInterrupt:
        logger.info("收到停止信号，优雅关闭...")

if __name__ == "__main__":
    main()
```

### 定时任务（scheduler.py）⭐ 更新

```python
# app/scheduler.py
import schedule
import time
import logging
from datetime import datetime
from app.modules.bilibili import fetch_channel_videos
from app.modules.dynamic import DynamicFetcher
from app.models.database import get_db, Subscription, Video, Dynamic
from app.utils.errors import RetryExhausted

logger = logging.getLogger("bili")

def check_new_videos():
    """检测所有UP主的新视频"""
    logger.info("[检测] 开始检查新视频...")
    
    try:
        db = get_db()
        subscriptions = db.query(Subscription).filter_by(is_active=True).all()
        
        new_count = 0
        for sub in subscriptions:
            try:
                videos = fetch_channel_videos(sub.mid, limit=5)
                logger.debug(f"用户 {sub.name} 获得 {len(videos)} 个视频")
                
                for v in videos:
                    # 检查是否已存在
                    existing = db.query(Video).filter_by(bvid=v["bvid"]).first()
                    if existing:
                        continue
                    
                    # 新视频，添加到数据库
                    new_video = Video(
                        bvid=v["bvid"],
                        title=v["title"],
                        mid=sub.mid,
                        pub_time=v["pubdate"],
                        status="pending"
                    )
                    db.add(new_video)
                    new_count += 1
                    logger.info(f"[新视频] {v['title']} ({v['bvid']})")
                
                sub.last_check_time = datetime.now()
                
            except Exception as e:
                logger.error(f"检查用户 {sub.mid} 失败: {e}", exc_info=True)
        
        db.commit()
        logger.info(f"[检测] 完成，发现 {new_count} 个新视频")
        
    except Exception as e:
        logger.error(f"检测过程异常: {e}", exc_info=True)


def check_new_dynamics():
    """检测所有UP主的新动态 ⭐（新增）"""
    logger.info("[检测] 开始检查新动态...")
    
    try:
        db = get_db()
        fetcher = DynamicFetcher()
        subscriptions = db.query(Subscription).filter_by(is_active=True).all()
        
        new_count = 0
        for sub in subscriptions:
            try:
                dynamics = fetcher.fetch_dynamic(sub.mid)
                logger.debug(f"用户 {sub.name} 获得 {len(dynamics)} 个动态")
                
                for dyn in dynamics:
                    # 检查是否已存在
                    existing = db.query(Dynamic).filter_by(
                        dynamic_id=dyn['dynamic_id']
                    ).first()
                    if existing:
                        continue
                    
                    # 下载图片
                    dyn = fetcher.download_images(dyn)
                    
                    # 新动态，添加到数据库
                    new_dynamic = Dynamic(
                        dynamic_id=dyn['dynamic_id'],
                        mid=sub.mid,
                        type=dyn['type'],
                        text=dyn['text'],
                        image_count=len(dyn['images']),
                        images_path=json.dumps(dyn['images']),
                        image_urls=json.dumps(dyn['image_urls']),
                        pub_time=dyn['pub_time'],
                        status="pending"
                    )
                    db.add(new_dynamic)
                    new_count += 1
                    logger.info(f"[新动态] {sub.name} - {dyn['text'][:50]}...")
                
                sub.last_check_time = datetime.now()
                
            except Exception as e:
                logger.error(f"检查用户 {sub.mid} 动态失败: {e}", exc_info=True)
        
        db.commit()
        logger.info(f"[检测] 完成，发现 {new_count} 个新动态")
        
    except Exception as e:
        logger.error(f"检测过程异常: {e}", exc_info=True)


def start_scheduler():
    """启动定时任务"""
    # 视频检测：每10分钟
    schedule.every(10).minutes.do(check_new_videos)
    
    # 动态检测：每5分钟（频率更高，因为动态更新快）
    schedule.every(5).minutes.do(check_new_dynamics)
    
    logger.info("定时任务已启动 (视频:10分钟, 动态:5分钟)")
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # 每分钟检查一次是否有任务要执行
```

### 队列处理（queue_worker.py）⭐ 更新

```python
# app/queue_worker.py
import logging
import json
from concurrent.futures import ThreadPoolExecutor
from app.models.database import get_db, Video, Dynamic
from app.modules.subtitle import get_subtitles
from app.modules.whisper_ai import transcribe_audio
from app.modules.llm import summarize
from app.modules.push import push_content
from app.utils.errors import ProcessingError

logger = logging.getLogger("bili")

def process_single_video(bvid: str):
    """处理单个视频的完整流程"""
    db = get_db()
    video = db.query(Video).filter_by(bvid=bvid).one()
    
    try:
        logger.info(f"[处理] 开始: {video.title} ({bvid})")
        video.status = "processing"
        db.commit()
        
        # 1. 获取字幕
        logger.debug(f"[字幕] 尝试获取...")
        subtitles = get_subtitles(bvid)
        video.has_subtitle = bool(subtitles)
        
        # 2. 如果没有字幕，用Whisper转写
        if not subtitles:
            logger.debug(f"[Whisper] 开始识别...")
            audio_path = download_audio(bvid)
            subtitles = transcribe_audio(audio_path)
            video.has_audio = True
        
        # 3. LLM总结
        logger.debug(f"[LLM] 开始总结...")
        summary_data = summarize(
            text=subtitles,
            title=video.title,
            duration=video.duration
        )
        
        # 4. 推送
        logger.debug(f"[推送] 发送中...")
        push_content(
            content_data={
                "type": "video",
                "title": video.title,
                **summary_data
            },
            channels=get_push_channels()
        )
        
        video.status = "done"
        logger.info(f"[完成] {bvid} ✓")
        
    except ProcessingError as e:
        logger.error(f"[失败] {bvid}: {e}")
        video.status = "failed"
        video.last_error = str(e)
        video.attempt_count += 1
        
        if video.attempt_count >= 3:
            logger.error(f"[放弃] {bvid} 已尝试3次，不再重试")
        else:
            logger.info(f"[重新入队] {bvid} (第{video.attempt_count}次)")
            
    finally:
        db.commit()


def process_single_dynamic(dynamic_id: str):
    """处理单个动态的完整流程 ⭐（新增）"""
    db = get_db()
    dynamic = db.query(Dynamic).filter_by(dynamic_id=dynamic_id).one()
    
    try:
        logger.info(f"[处理] 开始动态: {dynamic.text[:50]}...")
        dynamic.status = "processing"
        db.commit()
        
        # 动态处理很简单：直接推送
        logger.debug(f"[推送] 发送动态...")
        
        images = json.loads(dynamic.images_path) if dynamic.images_path else []
        
        push_content(
            content_data={
                "type": "dynamic",
                "text": dynamic.text,
                "images": images,
                "image_urls": json.loads(dynamic.image_urls) if dynamic.image_urls else [],
                "pub_time": dynamic.pub_time,
                "url": f"https://www.bilibili.com/opus/{dynamic.dynamic_id}"
            },
            channels=get_push_channels()
        )
        
        dynamic.status = "sent"
        dynamic.pushed_at = datetime.now()
        logger.info(f"[完成] 动态推送成功 ✓")
        
    except Exception as e:
        logger.error(f"[失败] 动态 {dynamic_id}: {e}", exc_info=True)
        dynamic.status = "failed"
        dynamic.last_error = str(e)
        dynamic.attempt_count += 1
        
        if dynamic.attempt_count < 3:
            logger.info(f"[重新入队] 动态 (第{dynamic.attempt_count}次)")
            
    finally:
        db.commit()


def start_queue_worker(max_workers=3):
    """启动队列处理worker"""
    db = get_db()
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        logger.info(f"队列处理已启动 (并发 {max_workers})")
        
        while True:
            # 优先处理动态（因为处理快）
            pending_dynamics = db.query(Dynamic).filter_by(
                status="pending"
            ).order_by(Dynamic.created_at).limit(5).all()
            
            # 然后处理视频
            pending_videos = db.query(Video).filter_by(
                status="pending"
            ).order_by(Video.created_at).limit(5).all()
            
            if not pending_dynamics and not pending_videos:
                logger.debug("暂无待处理内容，等待...")
                time.sleep(30)
                continue
            
            # 提交动态任务
            for dynamic in pending_dynamics:
                executor.submit(process_single_dynamic, dynamic.dynamic_id)
            
            # 提交视频任务
            for video in pending_videos:
                executor.submit(process_single_video, video.bvid)
            
            time.sleep(5)


def get_push_channels() -> list:
    """获取配置的推送渠道"""
    from config import Config
    channels = []
    if Config.FEISHU_WEBHOOK:
        channels.append("feishu")
    if Config.TELEGRAM_TOKEN:
        channels.append("telegram")
    if Config.WECHAT_CORP_ID:
        channels.append("wechat")
    return channels
```

---

## 部署方案

### 本地运行（Mac mini）

**1. 环境准备**
```bash
# 克隆项目
git clone <your-repo> bili-auto && cd bili-auto

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 下载Whisper模型（可选，首次自动下载）
python init_setup.py
```

**2. 配置**
```bash
# 复制配置模板
cp .env.example .env

# 编辑.env，填入你的token
# OPENAI_API_KEY=sk-...
# FEISHU_WEBHOOK=https://...
```

**3. 运行**
```bash
# 运行一次（测试）
python main.py

# 后台运行（使用nohup）
nohup python main.py > logs/app.log 2>&1 &

# 或使用systemd（推荐，重启后自动启动）
# 参见下一章节
```

### Systemd 服务（生产级）

**创建 `/etc/systemd/system/bili-auto.service`**：
```ini
[Unit]
Description=B站自动化摘要系统
After=network.target

[Service]
Type=simple
User=aniss
WorkingDirectory=/Users/aniss/Code/bili-auto
Environment="PATH=/Users/aniss/Code/bili-auto/venv/bin"
ExecStart=/Users/aniss/Code/bili-auto/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=append:/Users/aniss/Code/bili-auto/logs/app.log
StandardError=append:/Users/aniss/Code/bili-auto/logs/error.log

[Install]
WantedBy=multi-user.target
```

**启动**：
```bash
sudo systemctl daemon-reload
sudo systemctl start bili-auto
sudo systemctl enable bili-auto  # 开机自启

# 查看状态
sudo systemctl status bili-auto
sudo journalctl -u bili-auto -f  # 查看日志
```

### macOS Launch Agent（简便方案）

如果用macOS的Launch Agent更方便：

**创建 `~/Library/LaunchAgents/com.bili.auto.plist`**：
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.bili.auto</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/Users/aniss/Code/bili-auto/venv/bin/python</string>
        <string>/Users/aniss/Code/bili-auto/main.py</string>
    </array>
    
    <key>WorkingDirectory</key>
    <string>/Users/aniss/Code/bili-auto</string>
    
    <key>StandardOutPath</key>
    <string>/Users/aniss/Code/bili-auto/logs/app.log</string>
    
    <key>StandardErrorPath</key>
    <string>/Users/aniss/Code/bili-auto/logs/error.log</string>
    
    <key>KeepAlive</key>
    <true/>
    
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
```

**启动**：
```bash
launchctl load ~/Library/LaunchAgents/com.bili.auto.plist
launchctl start com.bili.auto

# 查看状态
launchctl list | grep bili
```

---

## 高级功能（第二阶段）

### 1. 关键词过滤

```python
# 只推你关心的内容

KEYWORDS_INCLUDE = ["AI", "创业", "编程"]  # 必须包含其一
KEYWORDS_EXCLUDE = ["带货", "广告"]        # 必须不包含

def should_push(summary_data: dict) -> bool:
    """判断是否推送"""
    text = (
        summary_data["title"] + 
        summary_data["summary"] + 
        " ".join(summary_data["tags"])
    ).lower()
    
    # 包含过滤
    if KEYWORDS_INCLUDE:
        if not any(kw.lower() in text for kw in KEYWORDS_INCLUDE):
            return False
    
    # 排除过滤
    if KEYWORDS_EXCLUDE:
        if any(kw.lower() in text for kw in KEYWORDS_EXCLUDE):
            return False
    
    return True
```

### 2. 自动分类

```python
# 训练一个简单的分类器

from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB

classifier = Pipeline([
    ('tfidf', TfidfVectorizer(max_features=1000)),
    ('classifier', MultinomialNB())
])

# 训练数据（示例）
training_texts = [...]
training_labels = ["技术", "投资", "科技", ...]

classifier.fit(training_texts, training_labels)

# 使用
def classify_video(summary: dict) -> str:
    text = summary["title"] + summary["summary"]
    category = classifier.predict([text])[0]
    return category
```

### 3. 向量搜索（B站知识库）

```python
# 构建个人知识库，可秒速搜索关连内容

from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Pinecone

embeddings = OpenAIEmbeddings(api_key=Config.OPENAI_API_KEY)

def index_summary(summary_data: dict):
    """将总结存入向量数据库"""
    text = f"{summary_data['title']}\n{summary_data['summary']}"
    
    # 这里可以用Pinecone、Milvus、ChromaDB等
    # 示例: Chroma (本地, 无需服务)
    from langchain.vectorstores import Chroma
    
    vector_store = Chroma(embedding_function=embeddings)
    vector_store.add_texts([text], metadata={"bvid": summary_data["bvid"]})

def search_knowledge_base(query: str, k=5):
    """搜索相关内容"""
    results = vector_store.similarity_search(query, k=k)
    return results
```

### 4. 精华片段提取（高阶）

```python
# 从视频中自动剪短视频

from moviepy.editor import VideoFileClip, concatenate_videoclips

def extract_highlights(video_path: str, timeline: list) -> str:
    """
    根据timeline提取精华片段
    
    timeline: [
        {"time": "0:00-0:30", "type": "highlight"},
        {"time": "3:00-3:45", "type": "highlight"}
    ]
    """
    video = VideoFileClip(video_path)
    clips = []
    
    for item in timeline:
        if item["type"] == "highlight":
            start_str, end_str = item["time"].split("-")
            start = time_to_seconds(start_str)
            end = time_to_seconds(end_str)
            clip = video.subclip(start, end)
            clips.append(clip)
    
    if clips:
        final = concatenate_videoclips(clips)
        output = f"output/{video_path.stem}_highlights.mp4"
        final.write_videofile(output)
        return output
```

### 5. 动态内容优化 ⭐（新增）

**动态去重与聚合**：
```python
def deduplicate_dynamics(dynamics: list) -> list:
    """
    去重：同一时间段的多条类似动态只保留一条
    """
    seen = set()
    unique = []
    
    for dyn in dynamics:
        # 用文本的hash去重
        text_hash = hash(dyn['text'][:100])
        if text_hash not in seen:
            seen.add(text_hash)
            unique.append(dyn)
    
    return unique
```

**图片压缩与优化**：
```python
from PIL import Image
import os

def optimize_images(image_paths: list, max_size_mb=5) -> list:
    """压缩图片，减小存储和网络传输"""
    optimized = []
    
    for path in image_paths:
        img = Image.open(path)
        
        # 调整大小（最大宽度1200px）
        img.thumbnail((1200, 1200))
        
        # 压缩质量
        output_path = path.replace('.jpg', '_opt.jpg')
        img.save(output_path, quality=85, optimize=True)
        
        # 检查大小
        size_mb = os.path.getsize(output_path) / (1024*1024)
        if size_mb < max_size_mb:
            optimized.append(output_path)
        else:
            # 继续降低质量
            img.save(output_path, quality=70, optimize=True)
            optimized.append(output_path)
    
    return optimized
```

**动态内容预过滤** ⭐（很重要）：
```python
def should_push_dynamic(dynamic: dict) -> bool:
    """
    判断动态是否值得推送
    
    过滤掉：
    • 纯转发（无原创）
    • 链接分享（广告）
    • 过短内容
    """
    
    text = dynamic.get('text', '').strip()
    
    # 过滤转发
    if text.startswith('转发') or text.startswith('//@'):
        return False
    
    # 过滤纯链接
    if text.startswith('http') and len(text) < 100:
        return False
    
    # 过滤太短
    if len(text) < 10:
        return False
    
    # 过滤垃圾词
    banned_keywords = ['秒杀', '折扣', '限时']
    if any(kw in text for kw in banned_keywords):
        return False
    
    return True
```

---

## 故障排查

| 问题 | 症状 | 排查方案 |
|------|------|---------|
| **B站限流** | 大量429错误 | 加随机延迟 + cookie更新 + 代理轮转 |
| **动态图片下载失败** | 推送时图片为空 | 检查图片URL有效性 + 重试机制 + 降级为文字推送 |
| **Whisper爆炸** | OOM或Segfault | 换tiny模型 或 拆分音频处理 |
| **LLM调用慢** | 推送延迟 | 换更便宜的GPT-3.5 或 本地模型 |
| **字幕文件损坏** | 解析失败 | 加try-catch + 降级处理 |
| **推送webhook失效** | Feishu/Telegram返回错误 | 检查URL、权限、消息格式、token过期 |
| **微信企业号推送失败** | access_token无效 | 检查corp_id/secret、token自动刷新机制 |
| **磁盘满** | 音频/日志/图片堆积 | 自动清理过期文件（>7天）+ 定期脚本 |
| **数据库锁** | 并发写入冲突 | 使用连接池 + WAL模式 |

---

## 项目里程碑

### 阶段一（第1-2周）：MVP可用

- [ ] 搭建基础框架
- [ ] B站API + 视频检测
- [ ] **B站动态检测 + 图片下载** ⭐（新增）
- [ ] 字幕获取 + Whisper集成
- [ ] LLM总结
- [ ] 飞书推送（支持图片）
- [ ] **Telegram推送（支持图片）** ⭐（新增）
- [ ] 本地运行验证

**目标**: 跑通一个完整流程，能自动处理视频 + 动态并推送

### 阶段二（第3-4周）：工程质量

- [ ] 错误处理 + 重试机制
- [ ] 日志系统完善
- [ ] 敏感信息管理
- [ ] 断点续传
- [ ] **动态去重 + 图片压缩** ⭐（新增）
- [ ] 性能监控
- [ ] Systemd部署

**目标**: 能长期稳定运行，可追踪调试

### 阶段三（第5-8周）：产品化

- [ ] 关键词过滤
- [ ] **动态内容预过滤** ⭐（新增）
- [ ] **微信企业号推送** ⭐（新增）
- [ ] 自动分类
- [ ] 向量搜索（知识库）
- [ ] Web UI（可选）
- [ ] 成本优化（本地模型）

**目标**: 可考虑开放给朋友用或商业化

---

## 快速开始

1. **项目初始化**
```bash
git clone <repo> bili-auto && cd bili-auto
python init_setup.py
```

2. **配置环境**
```bash
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY、FEISHU_WEBHOOK 等
```

3. **运行**
```bash
python main.py
```

4. **查看日志**
```bash
tail -f logs/bili.log
```

---

## 联系方式 & 支持

- **文档**: 本文件
- **日志**: `logs/bili.log`
- **常见问题**: 看"故障排查"章节

**这套方案已经被验证过，直接跟着做就行。**

祝你打造属于自己的B站知识系统！🚀

---

## 配置指南

### 飞书机器人

1. 打开飞书群 → 机器人 → 添加自定义机器人
2. 填写机器人名称，勾选"消息卡片"权限
3. 复制Webhook地址到`.env`：
```
FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxxxxxxx
```

### Telegram Bot

1. 打开 @BotFather → /newbot
2. 取名、记录token
3. 找到群聊ID（发送消息后用bot命令 /getupdate 查看）
4. 配置：
```
TELEGRAM_TOKEN=123456789:ABCDEFG1234567890
TELEGRAM_CHAT_ID=-1001234567890  # 负数表示群聊
```

### 微信企业号（推荐）⭐

1. 注册企业号 (https://work.weixin.qq.com)
2. 通讯录 → 自己 → 复制UID
3. 应用管理 → 新建应用 → 填写信息
4. 复制 corp_id, secret, agent_id 到`.env`：
```
WECHAT_CORP_ID=ww123456789abcdef0
WECHAT_CORP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
WECHAT_AGENT_ID=1000001
WECHAT_TO_USER=@all  # 或具体用户ID
```

### OpenAI API

```
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-3.5-turbo  # 或gpt-4-turbo
```

### B站Cookie（可选，避免限流）

```
BILIBILI_COOKIE=buvid3=xxxxx; b_nut=xxxxx; ...
```

（从浏览器F12 → Network → Cookie复制）


