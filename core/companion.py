"""陪伴回复生成模块。

输入：用户原话 + 分析结果 + 今日状态 + 最近对话 + 上一轮反馈
输出：2~5 句符合人格的回复；API 不可用时给本地兜底回复，保证页面可用。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.analyzer import friendly_error, get_llm_client, get_model_name, has_api_key
from prompts.companion_prompt import PERSONAS, build_companion_messages

MAX_SENTENCES = 5
_SENTENCE_PATTERN = re.compile(r"[^。！？!?.\n]+[。！？!?.\n]*")

FALLBACK_BY_SCENE = {
    "连败": "连续输几把确实容易上头，先停下来缓一会儿。等手感和心态都顺了再排，胜率会好看很多。",
    "获胜": "这把赢了值得高兴，刚才那波最关键的节奏确实打得好。今天的手感可以再享受一会儿。",
    "卡关": "卡在这里很正常，别急着硬冲。你把卡住的那一步说细一点，我陪你一起拆。",
    "组队": "和朋友一起打，节奏对不上太常见了。下一把开局先说好谁先手、谁保后排，会顺很多。",
    "游戏结束": "今天打了这么多把，收工也挺好。把今天的感觉记一下，明天再打会更清楚。",
    "无聊": "没手感的时候硬排容易掉分，换个模式或者看看新玩法也不错。你想轻松点还是想研究点什么？",
    "想聊天": "行，那就随便聊聊。你今天最想吐槽的是哪一把？",
    "想要攻略": "想要攻略的话，先告诉我是哪一步卡住，我给你拆成能马上试的几步。",
    "其他": "嗯，我在听。你多说一点当时的情况，我陪你一起看看。",
}

FALLBACK_BY_PERSONA = {
    "损友搭子": "行吧，就当给匹配机制上供了。你先说说这把到底怎么崩的？",
    "游戏教练": "先别急着开下一把。你把这局最难受的那个时间点说清楚，我们找一下问题在哪。",
    "冒险搭子": "地图这么大，迷路很正常。你先说说现在在哪，我陪你一起找路。",
    "温柔搭子": "嗯，我在。你今天打得已经够久了，先说说这局是怎么变成这样的。",
}


@dataclass
class Reply:
    """一次陪伴回复的结果。"""

    text: str
    source: str = "llm"   # llm / fallback
    notice: str = ""


def _limit_sentences(text: str) -> str:
    """兜住回复长度，最多保留 MAX_SENTENCES 句。"""
    sentences = [item.strip() for item in _SENTENCE_PATTERN.findall(text) if item.strip()]
    if len(sentences) <= MAX_SENTENCES:
        return text.strip()
    return "".join(sentences[:MAX_SENTENCES]).strip()


def fallback_reply(analysis, notice: str = "") -> Reply:
    """本地兜底回复：优先按场景挑，再按人格微调。"""
    text = FALLBACK_BY_SCENE.get(analysis.scene)
    if not text or analysis.scene in {"其他", "组队"}:
        text = FALLBACK_BY_PERSONA.get(analysis.persona, FALLBACK_BY_SCENE["其他"])
    return Reply(text=text, source="fallback", notice=notice)


def generate_reply(
    user_text: str,
    analysis,
    state_block: str = "",
    history_block: str = "",
    feedback_hint: str = "",
) -> Reply:
    """生成陪伴回复，失败时返回兜底回复。"""
    if not has_api_key():
        return fallback_reply(analysis, notice="没有配置可用的 API Key")

    if analysis.persona not in PERSONAS:
        analysis.persona = list(PERSONAS)[0]

    try:
        client = get_llm_client()
        response = client.chat.completions.create(
            model=get_model_name(),
            messages=build_companion_messages(user_text, analysis, state_block, history_block, feedback_hint),
            temperature=0.85,
            max_tokens=400,
        )
    except Exception as exc:
        return fallback_reply(analysis, notice=friendly_error(exc))

    text = (response.choices[0].message.content or "").strip()
    if not text:
        return fallback_reply(analysis, notice="模型返回了空回复")
    return Reply(text=_limit_sentences(text), source="llm")