"""
LLM 文本纠错模块
使用大语言模型对 Whisper 识别结果进行纠错和优化
"""
import json
from pathlib import Path
from app.utils.logger import get_logger
from config import Config

logger = get_logger("correction")

try:
    from openai import OpenAI, APIError
    if Config.OPENAI_API_KEY:
        client = OpenAI(api_key=Config.OPENAI_API_KEY, base_url=Config.OPENAI_BASE_URL)
    else:
        client = None
except ImportError:
    client = None
    logger.warning("openai 库未安装，无法使用 LLM 纠错")
except Exception as e:
    client = None
    logger.warning("OpenAI 初始化失败: %s", e)


def _load_default_prompt() -> str:
    """从 demo/prompt.txt 加载默认纠错 Prompt"""
    prompt_path = Path(__file__).resolve().parent.parent / "demo" / "prompt.txt"
    if prompt_path.exists():
        return prompt_path.read_text("utf-8")
    # 兜底
    return """你是一位精通港股市场、财经术语和网络口语的资深编辑。

任务：对用户提供的语音转文字记录进行处理，直接输出"纠正后的文本"和"提炼的大纲"两部分内容，无需任何额外解释、开场白或纠正清单。

处理要求：

1. 文本纠错与优化：
   - 将语音识别错误、口语化、不规范的表达，准确修正为正确的股票名称、公司简称、财经术语和流畅的书面语。
   - 修正范围包括但不限于：
     - 公司/股票名（如："闷牛" -> "蒙牛乳业/蒙牛"；"达市了" -> "达势股份/达美乐中国"）。
     - 专业术语（如："古都古西律" -> "股息派发率"；"踢" -> "做T"）。
     - 数字/时间（如："二五年" -> "2025年"）。
     - 口语/逻辑补全（如："多差不多了" -> "都差不多躺平了"）。

2. 内容大纲提炼：
   - 基于纠正后的清晰文本，用结构化大纲概括核心内容，逻辑应清晰反映UP主的复盘思路。
   - 大纲应涵盖：整体市况与心态、对每只重点股票的分析与操作、后续计划、投资策略总结等关键部分。

最终输出格式：
请严格且仅输出以下两个部分，以"---"分隔。

【纠正后文本】
[这里是纠正、优化后的完整通顺文本]

【内容大纲】
[这里是结构清晰、要点完整的层级化内容大纲]

请开始处理。"""


DEFAULT_CORRECTION_PROMPT = _load_default_prompt()


def correct_text(
    raw_text: str,
    video_title: str = "",
    custom_prompt: str = None
) -> dict:
    """
    使用 LLM 对识别文本进行纠错

    Args:
        raw_text: Whisper 识别的原始文本
        video_title: 视频标题（可选）
        custom_prompt: 自定义 prompt（可选，不填使用默认）

    Returns:
        dict: {
            "corrected_text": "纠正后的文本",
            "outline": "内容大纲",
            "success": True/False
        }
    """
    raw_text = (raw_text or "").strip()

    if not raw_text:
        logger.warning("原始文本为空，跳过纠错")
        return {
            "corrected_text": raw_text,
            "outline": "",
            "success": False
        }

    if not Config.OPENAI_API_KEY or not client:
        logger.info("未配置 OpenAI API，跳过 LLM 纠错")
        return {
            "corrected_text": raw_text,
            "outline": "",
            "success": False
        }

    try:
        logger.info("开始 LLM 纠错，原始文本长度: %d", len(raw_text))

        system_prompt = custom_prompt or DEFAULT_CORRECTION_PROMPT

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
        result = _parse_correction_response(response_text)

        # 如果纠正后文本太短，可能是模型没返回完整内容，降级使用原始文本
        if len(result["corrected_text"]) < len(raw_text) * 0.5:
            logger.warning("纠正后文本过短（可能被截断），使用原始文本")
            return {
                "corrected_text": raw_text,
                "outline": result["outline"],
                "success": True
            }

        logger.info("LLM 纠错完成，纠正后文本长度: %d", len(result["corrected_text"]))
        result["success"] = True
        return result

    except APIError as e:
        logger.warning("OpenAI API 调用失败，跳过纠错: %s", e)
        return {
            "corrected_text": raw_text,
            "outline": "",
            "success": False
        }
    except Exception as e:
        logger.error("LLM 纠错异常: %s", e, exc_info=True)
        return {
            "corrected_text": raw_text,
            "outline": "",
            "success": False
        }


def _parse_correction_response(text: str) -> dict:
    """解析 LLM 返回的纠错结果"""
    corrected_text = ""
    outline = ""

    # 尝试按分隔符拆分
    if "---" in text:
        parts = text.split("---")
        if len(parts) >= 2:
            part1 = parts[0].strip()
            part2 = parts[1].strip()

            # 提取纠正后文本
            if "【纠正后文本】" in part1:
                corrected_text = part1.split("【纠正后文本】")[-1].strip()
            else:
                corrected_text = part1

            # 提取大纲
            if "【内容大纲】" in part2:
                outline = part2.split("【内容大纲】")[-1].strip()
            else:
                outline = part2
    else:
        # 如果没有分隔符，尝试用关键词查找
        lines = text.splitlines()
        in_corrected = False
        in_outline = False
        corrected_lines = []
        outline_lines = []

        for line in lines:
            if "【纠正后文本】" in line:
                in_corrected = True
                in_outline = False
                continue
            if "【内容大纲】" in line:
                in_corrected = False
                in_outline = True
                continue

            if in_corrected:
                corrected_lines.append(line)
            elif in_outline:
                outline_lines.append(line)
            else:
                # 默认都当作纠正后文本
                corrected_lines.append(line)

        corrected_text = "\n".join(corrected_lines).strip()
        outline = "\n".join(outline_lines).strip()

    return {
        "corrected_text": corrected_text,
        "outline": outline
    }
