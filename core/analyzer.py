"""分析模块。

把用户的一句话拆成结构化结果：game / scene / emotion / intent / strategy，
自动模式下再决定这一轮用哪种人格。API 不可用时用本地规则兜底。
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from prompts.analyzer_prompt import (
    ANALYZER_SYSTEM_PROMPT,
    EMOTION_OPTIONS,
    GAME_OPTIONS,
    INTENT_OPTIONS,
    SCENE_OPTIONS,
    STRATEGY_OPTIONS,
    build_analyzer_user_prompt,
)

DEFAULT_MODEL = "deepseek-chat"
REQUEST_TIMEOUT = 45.0
ADVENTURE_GAMES = {"星露谷物语", "哈利波特", "双人成行"}


class LLMError(RuntimeError):
    """LLM 相关的统一错误类型，页面用它显示友好提示。"""


class AnalyzerError(LLMError):
    """分析阶段出错。"""


@dataclass
class Analysis:
    """一次分析的结果。"""

    game: str
    scene: str
    emotion: str
    intent: str
    strategy: str
    persona: str
    persona_mode: str = "auto"   # auto / manual
    source: str = "llm"          # llm / fallback
    notice: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _secret(name: str) -> str:
    """托管平台（Streamlit Community Cloud 等）把密钥放在 st.secrets 里。"""
    try:
        import streamlit as st

        value = st.secrets.get(name)
    except Exception:  # noqa: BLE001 - 本地没有 secrets.toml 时忽略
        return ""
    return str(value).strip() if value else ""


def _setting(name: str) -> str:
    """先读环境变量（.env），再读托管平台的 secrets。"""
    return (os.getenv(name) or _secret(name) or "").strip()


def has_api_key() -> bool:
    """页面上用来判断 API Key 是否已经配置好。"""
    load_dotenv(override=True, encoding="utf-8-sig")
    api_key = _setting("OPENAI_API_KEY")
    return bool(api_key) and "paste" not in api_key.lower() and api_key != "your_api_key_here"


def get_model_name() -> str:
    """取模型名，没配就用默认值。"""
    load_dotenv(override=True, encoding="utf-8-sig")
    return _setting("OPENAI_MODEL") or DEFAULT_MODEL


def get_llm_client() -> OpenAI:
    """创建 LLM 客户端。所有模块共用这一个函数，避免重复读配置。"""
    load_dotenv(override=True, encoding="utf-8-sig")
    api_key = _setting("OPENAI_API_KEY")
    if "://" in api_key:
        raise LLMError("OPENAI_API_KEY 里填的是网址，不是 Key。接口地址要写在 OPENAI_BASE_URL 那一行。")
    if not api_key or api_key == "your_api_key_here":
        env_abs = os.path.abspath(".env")
        state = "文件存在，但里面还是占位符" if os.path.exists(env_abs) else "没有找到这个文件"
        raise LLMError(
            "没有读到有效的 OPENAI_API_KEY（{0}：{1}）。本地请把 Key 填进 .env，"
            "线上请在 Streamlit 的 Secrets 里配置 OPENAI_API_KEY。".format(
                state, env_abs.replace(os.sep, "/")
            )
        )
    base_url = _setting("OPENAI_BASE_URL") or None
    try:
        return OpenAI(api_key=api_key, base_url=base_url, timeout=REQUEST_TIMEOUT)
    except Exception as exc:
        raise LLMError(f"初始化 LLM 客户端失败：{exc}") from exc


def friendly_error(exc: Exception) -> str:
    """把底层异常翻成用户能看懂的一句话。"""
    text = str(exc)
    lowered = text.lower()
    if "401" in text or "authentication" in lowered or "invalid" in lowered and "api key" in lowered:
        return "API Key 无效或已过期"
    if "402" in text or "insufficient balance" in lowered:
        return "账户余额不足"
    if "429" in text or "rate limit" in lowered:
        return "调用太频繁，被限流了"
    if "timeout" in lowered or "timed out" in lowered:
        return "请求超时，可以再试一次"
    return f"调用失败：{text[:180]}"


def select_strategy(scene: str, emotion: str, intent: str, game: str = "") -> str:
    """根据场景、情绪、意图选本轮陪伴策略（规则固定，方便调试）。"""
    if scene == "获胜" or intent == "分享喜悦" or emotion in {"开心", "兴奋"}:
        return "分享喜悦"
    if scene in {"卡关", "想要攻略"} or intent == "寻求攻略":
        return "游戏指导"
    if emotion == "焦虑" or scene == "游戏结束":
        return "鼓励休息"
    if scene == "连败" or emotion == "挫败":
        return "情绪安抚"
    if emotion == "烦躁":
        return "轻度吐槽"
    if scene in {"想聊天", "无聊"} or intent == "寻求聊天":
        return "冒险陪伴" if game in ADVENTURE_GAMES else "主动聊天"
    if intent == "寻求建议":
        return "游戏指导"
    return "主动聊天"


def select_persona(game: str, scene: str, emotion: str, intent: str) -> str:
    """自动模式下挑一个最合适的人格。"""
    if intent == "寻求攻略" or scene in {"卡关", "想要攻略"}:
        return "游戏教练"
    if emotion in {"焦虑", "挫败"} or scene in {"连败", "游戏结束"}:
        return "温柔搭子"
    if emotion == "烦躁":
        return "损友搭子"
    if intent == "寻求建议":
        return "游戏教练"
    if game in ADVENTURE_GAMES:
        return "冒险搭子"
    if scene == "获胜" or emotion in {"开心", "兴奋"}:
        return "损友搭子"
    return "温柔搭子"


SCENE_KEYWORDS = {
    "获胜": ["上王者", "终于上", "赢了", "吃鸡", "打赢", "上分了", "通关了"],
    "连败": ["连跪", "连败", "一直输", "三连", "四连", "五连", "掉分", "掉星", "输了一晚上"],
    "卡关": ["卡关", "卡了", "卡住", "卡在", "打不过", "过不去", "过不了"],
    "组队": ["组队", "开黑", "和朋友一起打", "一起玩"],
    "游戏结束": ["不打了", "打完了", "下线", "收工", "今天到此"],
    "无聊": ["无聊", "没意思", "没劲"],
    "想聊天": ["想聊天", "陪我聊", "聊聊天", "想玩点游戏", "晚上想玩"],
    "想要攻略": ["攻略", "怎么打", "怎么过", "教学", "出装", "怎么玩"],
    "其他": ["队友"],
}

EMOTION_KEYWORDS = {
    "烦躁": ["烦死", "好烦", "很烦", "气死", "火大", "受不了", "暴躁", "烦死"],
    "挫败": ["打不过", "过不去", "完全不知道", "太难", "自闭", "崩了", "卡了半"],
    "焦虑": ["掉星", "掉分", "要掉", "来不及", "紧张", "怕"],
    "兴奋": ["终于", "太爽", "上王者", "成功了", "赢了"],
    "开心": ["开心", "高兴", "舒服"],
    "无聊": ["无聊", "没意思", "没劲"],
    "平静": [],
}

INTENT_KEYWORDS = {
    "寻求攻略": ["怎么过", "怎么打", "怎么赢", "攻略", "教学", "出装", "完全不知道"],
    "倾诉": ["烦死", "气死", "受不了", "我真的", "心态", "烦"],
    "分享喜悦": ["终于", "成功了", "上王者", "太爽", "赢了"],
    "寻求安慰": ["难受", "想哭", "崩了", "自闭"],
    "寻求建议": ["建议", "该不该", "要不要", "推荐", "有什么好玩"],
    "寻求聊天": ["想聊天", "陪我聊", "想玩点游戏", "无聊", "随便聊聊"],
}


def _match_keywords(text: str, table: dict[str, list[str]], fallback: str) -> str:
    """按表里的顺序找第一个命中的关键词，命中不到就用兜底值。"""
    for label, keywords in table.items():
        if any(word in text for word in keywords):
            return label
    return fallback


def _pick(value: Any, options: list[str], fallback: str) -> str:
    text = str(value or "").strip()
    return text if text in options else fallback


def fallback_analysis(
    user_text: str,
    game: str = "其他",
    manual_persona: str | None = None,
    notice: str = "",
) -> Analysis:
    """纯规则的本地分析，API 不可用或做测试时使用。"""
    scene = _match_keywords(user_text, SCENE_KEYWORDS, "其他")
    emotion = _match_keywords(user_text, EMOTION_KEYWORDS, "平静")
    intent = _match_keywords(user_text, INTENT_KEYWORDS, "其他")
    resolved_game = game if game in GAME_OPTIONS else "其他"
    return Analysis(
        game=resolved_game,
        scene=scene,
        emotion=emotion,
        intent=intent,
        strategy=select_strategy(scene, emotion, intent, resolved_game),
        persona=manual_persona or select_persona(resolved_game, scene, emotion, intent),
        persona_mode="manual" if manual_persona else "auto",
        source="fallback",
        notice=notice,
    )


def parse_json_content(content: str) -> dict[str, Any]:
    """尽量从模型输出里抠出 JSON，兼容代码块和多余文字。"""
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[A-Za-z]*\s*", "", text)
        text = re.sub(r"```\s*$", "", text).strip()
    if not text:
        raise AnalyzerError("模型返回了空的分析结果")
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        text = match.group(0)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AnalyzerError("模型返回的内容不是合法 JSON") from exc
    if not isinstance(data, dict):
        raise AnalyzerError("模型返回的 JSON 结构不对")
    return data


def _analysis_from_llm(data: dict[str, Any], game: str, manual_persona: str | None) -> Analysis:
    scene = _pick(data.get("scene"), SCENE_OPTIONS, "其他")
    emotion = _pick(data.get("emotion"), EMOTION_OPTIONS, "不确定")
    intent = _pick(data.get("intent"), INTENT_OPTIONS, "其他")
    resolved_game = game if game in GAME_OPTIONS and game != "其他" else _pick(data.get("game"), GAME_OPTIONS, "其他")
    strategy = _pick(data.get("strategy"), STRATEGY_OPTIONS, select_strategy(scene, emotion, intent, resolved_game))
    return Analysis(
        game=resolved_game,
        scene=scene,
        emotion=emotion,
        intent=intent,
        strategy=strategy,
        persona=manual_persona or select_persona(resolved_game, scene, emotion, intent),
        persona_mode="manual" if manual_persona else "auto",
        source="llm",
    )


def call_analyzer_llm(
    user_text: str,
    game: str,
    state_block: str = "",
    history_block: str = "",
    feedback_hint: str = "",
) -> dict[str, Any]:
    """调用 LLM 做分析，返回解析后的字典。"""
    client = get_llm_client()
    messages = [
        {"role": "system", "content": ANALYZER_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": build_analyzer_user_prompt(user_text, game, state_block, history_block, feedback_hint),
        },
    ]
    try:
        response = client.chat.completions.create(
            model=get_model_name(),
            messages=messages,
            temperature=0.2,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        raise AnalyzerError(friendly_error(exc)) from exc
    content = response.choices[0].message.content or ""
    return parse_json_content(content)


def analyze_user_input(
    user_text: str,
    game: str,
    state_block: str = "",
    history_block: str = "",
    feedback_hint: str = "",
    manual_persona: str | None = None,
) -> Analysis:
    """分析入口：优先用 LLM，失败时用本地规则兜底（没配 Key 时直接报错提示）。"""
    if not has_api_key():
        raise LLMError(
            "没有读到有效的 OPENAI_API_KEY（{0}）。请把 Key 填进 .env，保存后刷新页面。".format(
                os.path.abspath(".env").replace(os.sep, "/")
            )
        )
    try:
        data = call_analyzer_llm(user_text, game, state_block, history_block, feedback_hint)
    except LLMError as exc:
        return fallback_analysis(user_text, game, manual_persona, notice=str(exc))
    return _analysis_from_llm(data, game, manual_persona)