import json
import os
from app.utils.logger import get_logger
from config import Config

logger = get_logger("llm")

try:
    from openai import OpenAI, APIError
    client = OpenAI(api_key=Config.OPENAI_API_KEY, base_url=Config.OPENAI_BASE_URL)
except ImportError:
    client = None
except Exception as e:
    logger.warning("OpenAI 初始化失败: %s", e)
    client = None


def summarize(text: str, title: str = "", duration: int = 0) -> dict:
    """
    使用LLM总结视频内容，返回结构化数据
    
    Args:
        text: 视频字幕或转录文本
        title: 视频标题
        duration: 视频时长（分钟）
    
    Returns:
        dict with keys: summary, key_points, tags, insights, duration_minutes
    """
    text = (text or "").strip()
    if not text:
        logger.warning("文本为空，返回默认摘要")
        return _default_summary(title, duration)

    # 尝试使用OpenAI API
    if Config.OPENAI_API_KEY and client:
        try:
            return _summarize_with_openai(text, title, duration)
        except APIError as e:
            logger.warning("OpenAI API 调用失败 (%s)，使用本地回退方案", str(e)[:50])
        except Exception as e:
            logger.error("LLM 调用异常: %s", e, exc_info=True)
    
    # 本地简易回退
    logger.info("使用本地简易摘要")
    return _summarize_local(text, title, duration)


def _summarize_with_openai(text: str, title: str, duration: int) -> dict:
    """使用OpenAI API进行总结"""
    
    # 截断过长文本，避免超出token限制
    text_for_llm = text[:80000]
    
    system_prompt = """你是一个高质量内容分析助手。请基于提供的视频字幕或转录内容，生成结构化的总结。
    
    你必须返回一个JSON格式的响应，包含以下字段：
    - summary: 一句话核心观点，50-100字
    - key_points: 数组，3-5个关键要点，每个30-50字
    - tags: 数组，最多5个标签，要有区分度
    - insights: 1-2条有价值的洞察或拓展思考
    
    保证输出是有效的JSON格式。"""
    
    user_prompt = f"""【视频信息】
标题：{title}
时长：{duration} 分钟

【字幕/转录文本】
{text_for_llm}

请分析上述内容，返回JSON格式的结构化摘要。"""
    
    response = client.chat.completions.create(
        model=Config.OPENAI_MODEL or "gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3,
        max_tokens=800,
        timeout=30
    )
    
    response_text = response.choices[0].message.content.strip()
    logger.debug("OpenAI 原始响应: %s", response_text[:200])
    
    # 尝试解析JSON响应
    try:
        # 尝试直接解析
        result = json.loads(response_text)
    except json.JSONDecodeError:
        # 尝试提取JSON块
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group())
            except json.JSONDecodeError:
                logger.warning("无法解析JSON响应，使用本地回退")
                return _summarize_local(text, title, duration)
        else:
            logger.warning("响应中未找到JSON，使用本地回退")
            return _summarize_local(text, title, duration)
    
    # 验证和规范化返回数据
    summary = (result.get("summary", "") or "").strip()[:200]
    key_points = result.get("key_points", [])
    if not isinstance(key_points, list):
        key_points = [str(key_points)]
    key_points = [str(p).strip() for p in key_points[:5] if str(p).strip()]
    
    tags = result.get("tags", [])
    if not isinstance(tags, list):
        tags = [str(tags)]
    tags = [str(t).strip() for t in tags[:5] if str(t).strip()]

    # 处理 insights 可能是 list 或 string 的情况
    insights_val = result.get("insights", "")
    if isinstance(insights_val, list):
        insights = "\n".join([str(x) for x in insights_val]).strip()[:500]
    else:
        insights = (str(insights_val) or "").strip()[:500]
    
    logger.info("LLM 总结完成: %d字摘要, %d个要点, %d个标签", 
                len(summary), len(key_points), len(tags))
    
    return {
        "summary": summary,
        "key_points": key_points,
        "tags": tags,
        "insights": insights,
        "duration_minutes": duration
    }


def _summarize_local(text: str, title: str, duration: int) -> dict:
    """本地简易总结（无需API调用）"""
    
    # 分句
    sentences = text.replace("。", "。\n").replace("！", "！\n").replace("？", "？\n").splitlines()
    sentences = [s.strip() for s in sentences if s.strip()]
    
    # 提取摘要（前几句）
    summary = "。".join(sentences[:5])
    if summary and not summary.endswith("。"):
        summary += "。"
    summary = summary[:200]
    
    # 提取关键点
    key_points = [s[:80] for s in sentences[0:5] if len(s) > 10]
    
    # 简单标签提取（基于关键词）
    tags = []
    keywords = {
        "AI": ["人工智能", "AI", "机器学习", "深度学习", "神经网络"],
        "技术": ["技术", "开发", "编程", "代码", "算法"],
        "创业": ["创业", "融资", "投资", "创始人", "公司"],
        "产品": ["产品", "功能", "用户", "体验", "设计"],
        "观点": ["认为", "看法", "观点", "思考", "分析"]
    }
    
    text_lower = text.lower()
    for tag, keywords_list in keywords.items():
        if any(kw in text_lower for kw in keywords_list):
            tags.append(tag)
    
    tags = tags[:5] if tags else ["其他"]
    
    logger.info("本地摘要完成: %d字摘要, %d个要点, %d个标签", 
                len(summary), len(key_points), len(tags))
    
    return {
        "summary": summary,
        "key_points": key_points[:5],
        "tags": tags,
        "insights": "此总结由本地简易算法生成，可启用 OPENAI_API_KEY 获得更高质量的分析。",
        "duration_minutes": duration
    }


def _default_summary(title: str, duration: int) -> dict:
    """空白文本时的默认返回"""
    return {
        "summary": f"无法获取字幕或转录内容，标题：{title}",
        "key_points": [],
        "tags": [],
        "insights": "请检查视频字幕或音频文件。",
        "duration_minutes": duration
    }
