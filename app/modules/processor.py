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
    """加载处理 Prompt（纠错 + 总结一起）"""
    return """你是一位精通港股市场、财经术语和网络口语的资深内容分析师。

任务：对用户提供的语音转文字记录进行处理，直接输出以下三个部分内容，无需任何额外解释或开场白。

处理要求：

1. 文本纠错与优化：
   - 将语音识别错误、口语化、不规范的表达，准确修正为正确的股票名称、公司简称、财经术语和流畅的书面语。
   - 纠正后, 应该为通顺、专业、清晰的文本，便于后续分析和总结。
   - 修正范围包括但不限于：
     - 公司/股票名（如："闷牛" -> "蒙牛乳业/蒙牛"；"达市" -> "达势股份/达美乐中国"）。
     - 专业术语（如："古都古西律" -> "股息派发率"；"踢" -> "做T"）。
     - 数字/时间（如："二五年" -> "2025年"）。
     - 口语/逻辑补全（如："多差不多了" -> "都差不多了"）。

2. 内容总结：
   - summary: 一句话核心观点，50-100字
   - details: 
        1. 基于纠正后的清晰文本，用结构化大纲概括核心内容，并尽量详细的描述UP主的复盘或者选股思路
        2. 至少应涵盖：整体市况与心态、核心投资理念、对每只重点股票的分析与操作、后续计划、投资策略、反思和教训、总结展望等部分
        3. **每一部分都要尽可能的详细**, **不能漏掉**任何一个重点股票的分析与操作细节，不能漏掉UP主的任何一个投资策略和投资理念
        4. 使用 markdown 格式，便于后续展示
   - key_points: 数组，3-5个关键要点，每个30-50字
   - tags: 数组，最多5个标签，要有区分度
   - insights: 1-2条有价值的洞察或拓展思考

最终输出格式：
请严格且仅输出以下两个部分，以"---"分隔。

【纠正后文本】
[这里是纠正、优化后的完整通顺文本]

---

【内容总结】
{
  "summary": "一句话核心观点",
  "details": "详细总结内容, 应涵盖：整体市况与心态、对每只重点股票的分析与操作、后续计划、投资策略总结等关键部分。",
  "key_points": ["要点1", "要点2", "要点3"],
  "tags": ["标签1", "标签2"],
  "insights": "洞察内容"
}

请开始处理。"""


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
            "tags": [],
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
            "tags": [],
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
            max_tokens=12000,
            timeout=120
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
    """解析处理响应"""
    parts = text.split("---")

    corrected_text = raw_text
    summary_data = {
        "summary": "",
        "details": "",
        "key_points": [],
        "tags": [],
        "insights": ""
    }

    if len(parts) >= 2:
        # 第一部分：纠正后文本
        part1 = parts[0].strip()
        if "【纠正后文本】" in part1:
            extracted = part1.split("【纠正后文本】")[-1].strip()
            if len(extracted) > len(raw_text) * 0.5:
                corrected_text = extracted

        # 第二部分：总结
        part2 = "---".join(parts[1:]).strip()
        if "【内容总结】" in part2:
            json_str = part2.split("【内容总结】")[-1].strip()
            # 提取 JSON
            json_match = re.search(r'\{.*\}', json_str, re.DOTALL)
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

    tags = summary_data.get("tags", [])
    if not isinstance(tags, list):
        tags = [str(tags)]
    tags = [str(t).strip() for t in tags[:5] if str(t).strip()]

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
        "tags": tags,
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
        "tags": tags,
        "insights": "此总结由本地简易算法生成，可启用 OPENAI_API_KEY 获得更高质量的分析。",
        "success": False
    }
