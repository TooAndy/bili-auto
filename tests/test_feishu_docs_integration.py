#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书文档集成测试

注意：此测试会真实调用飞书 API，需要配置以下环境变量：
- FEISHU_APP_ID
- FEISHU_APP_SECRET
- FEISHU_DOCS_ENABLED=true
- FEISHU_DOCS_FOLDER_TOKEN (可选)

运行方式：
    python3 -m pytest tests/test_feishu_docs_integration.py -v --tb=short -m integration
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.modules import feishu_docs
from config import Config


def is_feishu_configured() -> bool:
    """检查飞书配置是否完整"""
    return bool(
        Config.FEISHU_APP_ID
        and Config.FEISHU_APP_SECRET
        and Config.FEISHU_DOCS_ENABLED
    )


@pytest.mark.integration
@pytest.mark.skipif(not is_feishu_configured(), reason="飞书配置不完整")
def test_upload_markdown_real_api():
    """集成测试：使用真实 API 上传 Markdown 文件"""
    print("\n" + "=" * 70)
    print("测试：使用真实飞书 API 上传 Markdown")
    print("=" * 70)

    title = "测试文档 - bili-auto 集成测试"
    content = """# 测试文档

这是一个由 bili-auto 集成测试创建的文档。

## 测试内容

- 列表项 1
- 列表项 2
- 列表项 3

---

**粗体文字**

普通段落内容。
"""

    folder_token = Config.FEISHU_DOCS_FOLDER_TOKEN or None

    print(f"\n标题: {title}")
    print(f"文件夹: {folder_token or '根目录'}")
    print("\n正在上传文档...")

    result = feishu_docs.upload_markdown_to_feishu(title, content, folder_token)

    assert result is not None, "文档上传失败，返回 None"
    assert "file_token" in result
    assert "url" in result

    print(f"\n✅ 文档上传成功!")
    print(f"   文件 Token: {result['file_token']}")
    print(f"   文件链接: {result['url']}")


@pytest.mark.integration
@pytest.mark.skip(reason="需要真实的飞书文件夹 token，当前配置无效")
def test_push_video_summary_real_api():
    """集成测试：使用真实 API 推送视频总结"""
    print("\n" + "=" * 70)
    print("测试：使用真实飞书 API 推送视频总结")
    print("=" * 70)

    video_title = "测试视频：这是一个很棒的视频"
    bvid = "BVTEST001"
    uploader_name = "测试UP主"

    markdown_content = f"""# {video_title}

**URL**: https://www.bilibili.com/video/{bvid}

**UP主**: {uploader_name}

**发布时间**: 2026-04-01 12:00:00

---

## 内容总结

这是一个测试视频的总结内容。

### 要点

- 要点一：这是第一个要点
- 要点二：这是第二个要点
- 要点三：这是第三个要点

### 详细内容

这里是详细的视频内容描述。
可以包含很多行文字。
"""

    print(f"\n视频标题: {video_title}")
    print(f"BV号: {bvid}")
    print(f"UP主: {uploader_name}")
    print("\n正在创建文档...")

    result = feishu_docs.push_video_summary_to_doc(
        title=video_title,
        markdown_content=markdown_content,
        bvid=bvid,
        uploader_name=uploader_name
    )

    assert result is not None, "文档创建失败，返回 None"
    assert "file_token" in result
    assert "url" in result

    print(f"\n✅ 视频总结文档创建成功!")
    print(f"   文件链接: {result['url']}")
