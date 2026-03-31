"""
统一内容处理模块
整合 LLM 纠错 + 总结功能，只需一次 API 调用
"""
import json
import re
from pathlib import Path
from app.utils.logger import get_logger
from config import Config

logger = get_logger("processor")

try:
    from openai import OpenAI, APIError
    if Config.OPENAI_API_KEY:
        client = OpenAI(api_key=Config.OPENAI_API_KEY, base_url=Config.OPENAI_BASE_URL)
    else:
        client = None
except ImportError:
    client = None
    logger.warning("openai 库未安装，无法使用 LLM 处理")
except Exception as e:
    client = None
    logger.warning("OpenAI 初始化失败: %s", e)


def _load_process_prompt() -> str:
    """加载处理 Prompt（从 docs/prompt.md 读取）"""
    prompt_path = Path(__file__).parent.parent.parent / "docs" / "prompt.md"
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error("加载 prompt.md 失败: %s", e)
        # 返回一个简单的备用 prompt
        return "你是一个专业的内容处理助手，请将输入文本处理为结构化JSON格式。"


DEFAULT_PROCESS_PROMPT = _load_process_prompt()


def process_text(
    raw_text: str,
    video_title: str = "",
    duration: int = 0,
    custom_prompt: str = None
) -> dict:
    """
    统一处理：纠错 + 总结，一次 API 调用完成

    Args:
        raw_text: Whisper 识别的原始文本
        video_title: 视频标题
        duration: 视频时长（分钟）
        custom_prompt: 自定义 prompt（可选）

    Returns:
        dict: {
            "corrected_text": "纠正后的文本",
            "summary": "摘要",
            "details": "详细总结内容",
            "key_points": [],
            "stocks": [],
            "insights": "",
            "success": True/False
        }
    """
    raw_text = (raw_text or "").strip()

    if not raw_text:
        logger.warning("原始文本为空")
        return {
            "corrected_text": "",
            "summary": "",
            "details": "",
            "key_points": [],
            "stocks": [],
            "insights": "",
            "success": False
        }

    if not Config.OPENAI_API_KEY or not client:
        logger.info("未配置 OpenAI API，使用本地简易处理")
        return _process_local(raw_text, video_title, duration)

    try:
        logger.info("开始 LLM 处理，原始文本长度: %d", len(raw_text))

        system_prompt = custom_prompt or DEFAULT_PROCESS_PROMPT

        user_prompt = f"""【视频标题】
{video_title or "未提供"}

【语音识别原始文本】
{raw_text}"""

        response = client.chat.completions.create(
            model=Config.OPENAI_MODEL or "gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=120000,
            timeout=1200
        )

        response_text = response.choices[0].message.content.strip()
        logger.debug("LLM 响应: %s", response_text[:300])

        # 解析响应
        result = _parse_process_response(response_text, raw_text)

        logger.debug("LLM 处理完成，摘要: %d字", len(result.get("summary", "")))
        result["success"] = True
        return result

    except APIError as e:
        logger.warning("OpenAI API 调用失败，使用本地回退: %s", e)
        return _process_local(raw_text, video_title, duration)
    except Exception as e:
        logger.error("LLM 处理异常: %s", e, exc_info=True)
        return _process_local(raw_text, video_title, duration)


def _parse_process_response(text: str, raw_text: str) -> dict:
    """解析处理响应（新格式：直接返回 JSON）"""
    corrected_text = raw_text
    summary_data = {
        "summary": "",
        "details": "",
        "key_points": [],
        "stocks": [],
        "insights": ""
    }

    # 新格式：直接提取 JSON
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group())
            summary_data.update(parsed)
        except json.JSONDecodeError:
            pass

    # 规范化数据
    summary = str(summary_data.get("summary", "")).strip()[:200]
    details = str(summary_data.get("details", "")).strip()

    key_points = summary_data.get("key_points", [])
    if not isinstance(key_points, list):
        key_points = [str(key_points)]
    key_points = [str(p).strip() for p in key_points[:5] if str(p).strip()]

    stocks = summary_data.get("stocks", [])
    if not isinstance(stocks, list):
        stocks = [str(stocks)]
    stocks = [str(s).strip() for s in stocks[:10] if str(s).strip()]

    insights_val = summary_data.get("insights", "")
    if isinstance(insights_val, list):
        insights = "\n".join([str(x) for x in insights_val]).strip()[:500]
    else:
        insights = (str(insights_val) or "").strip()[:500]

    return {
        "corrected_text": corrected_text,
        "summary": summary,
        "details": details,
        "key_points": key_points,
        "stocks": stocks,
        "tags": [],  # 保持兼容，返回空 tags
        "insights": insights
    }


def _process_local(raw_text: str, video_title: str, duration: int) -> dict:
    """本地简易处理（无 API）"""
    # 分句
    sentences = raw_text.replace("。", "。\n").replace("！", "！\n").replace("？", "？\n").splitlines()
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

    text_lower = raw_text.lower()
    for tag, keywords_list in keywords.items():
        if any(kw in text_lower for kw in keywords_list):
            tags.append(tag)

    tags = tags[:5] if tags else ["其他"]

    logger.info("本地处理完成: %d字摘要, %d个要点, %d个标签",
                len(summary), len(key_points), len(tags))

    return {
        "corrected_text": raw_text,
        "summary": summary,
        "details": "",
        "key_points": key_points[:5],
        "stocks": [],
        "tags": tags,
        "insights": "此总结由本地简易算法生成，可启用 OPENAI_API_KEY 获得更高质量的分析。",
        "success": False
    }
