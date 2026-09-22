"""GameBuddy —— AI 游戏陪伴 Agent 的 Streamlit 前端。

页面顺序：标题 → 开局设置 → 输入框 → 搭子的回应（含状态分析和反馈）。
决策逻辑在 core/，提示词在 prompts/，这个文件只做编排和界面。
"""

from __future__ import annotations

import streamlit as st

from core.analyzer import LLMError, analyze_user_input, has_api_key
from core.companion import generate_reply
from core.game_state import GameState
from core.memory import Memory
from prompts.analyzer_prompt import GAME_OPTIONS
from prompts.companion_prompt import PERSONA_OPTIONS, persona_key_from_option, persona_title

st.set_page_config(
    page_title="GameBuddy｜AI 游戏陪伴 Agent",
    page_icon="🎮",
    layout="centered",
    initial_sidebar_state="collapsed",
)

PAGE_CSS = """
<style>
.block-container { max-width: 900px; padding-top: 2.2rem; padding-bottom: 4rem; }
.gb-hero-title { font-size: 2.1rem; font-weight: 800; letter-spacing: .3px; }
.gb-hero-sub { color: #8b93a7; margin-bottom: 1.8rem; }
.gb-section { color: #96a0b5; font-size: .78rem; font-weight: 700; letter-spacing: .12em; margin-bottom: .35rem; }
.gb-chip { display: inline-block; background: #1d2432; border: 1px solid #2a3242; border-radius: 999px; padding: 3px 12px; font-size: .8rem; margin: 0 8px 8px 0; color: #b8c2d6; }
.gb-said { color: #8b93a7; font-size: .84rem; margin-bottom: .5rem; }
</style>
"""
st.markdown(PAGE_CSS, unsafe_allow_html=True)

ENV_HINT = "请把 D:/gamebuddy/.env 里的 OPENAI_API_KEY 换成真实 Key（DeepSeek 是 sk- 开头），保存后刷新页面。"

QUICK_PROMPTS = [
    "三连跪了，队友一直送，我真的烦死了",
    "终于上王者了，打了一晚上终于成功了",
    "双人成行这个地方卡了半个小时了，完全不知道怎么过",
    "今天晚上想玩点游戏",
]

DEFAULT_GAME = GAME_OPTIONS[0]
DEFAULT_PERSONA = PERSONA_OPTIONS[0]


def init_session() -> None:
    """初始化会话级状态。"""
    st.session_state.setdefault("memory", Memory())
    st.session_state.setdefault("game_state", GameState())
    st.session_state.setdefault("notice", "")
    st.session_state.setdefault("last_notice", "")
    st.session_state.setdefault("game_choice", DEFAULT_GAME)
    st.session_state.setdefault("persona_choice", DEFAULT_PERSONA)
    st.session_state.setdefault("user_input", "")


def fill_input(text: str) -> None:
    """快速体验：把示例填进输入框。"""
    st.session_state["user_input"] = text


def queue_submit() -> None:
    """开始陪伴：把输入排队交给主流程，并清空输入框。"""
    text = (st.session_state.get("user_input") or "").strip()
    if text:
        st.session_state["pending_submit"] = text
    st.session_state["user_input"] = ""


def add_win() -> None:
    st.session_state["game_state"].add_win()


def add_loss() -> None:
    st.session_state["game_state"].add_loss()


def reset_today() -> None:
    st.session_state["game_state"].reset()


def set_feedback(value: str) -> None:
    """记录反馈，下一轮会写进 Prompt。"""
    st.session_state["memory"].set_feedback(value)


def clear_chat() -> None:
    """清空当前会话的对话、分析和提示。"""
    st.session_state["memory"].reset()
    st.session_state["notice"] = ""
    st.session_state["last_notice"] = ""
    st.session_state["user_input"] = ""


def handle_submit(user_text: str, game: str, persona_option: str) -> None:
    """完整流程：用户输入 → 分析 → 选策略/人格 → 生成回复 → 写入记忆。"""
    memory: Memory = st.session_state["memory"]
    state: GameState = st.session_state["game_state"]
    manual_persona = persona_key_from_option(persona_option)

    memory.add_user(user_text)
    history = memory.recent_text(limit=8)

    with st.spinner("正在理解这一局…"):
        try:
            analysis = analyze_user_input(
                user_text=user_text,
                game=game,
                state_block=state.as_prompt_block(),
                history_block=history,
                feedback_hint=memory.feedback_hint(),
                manual_persona=manual_persona,
            )
        except LLMError as exc:
            st.session_state["notice"] = f"分析失败：{exc}"
            return

    with st.spinner("正在组织回复…"):
        reply = generate_reply(
            user_text=user_text,
            analysis=analysis,
            state_block=state.as_prompt_block(),
            history_block=history,
            feedback_hint=memory.feedback_hint(),
        )

    memory.add_assistant(reply.text)
    memory.set_analysis(analysis)
    state.mood = analysis.emotion
    state.persona = analysis.persona

    notices = []
    if analysis.source == "fallback" and analysis.notice:
        notices.append(f"分析用了本地兜底（{analysis.notice}）")
    if reply.source == "fallback" and reply.notice:
        notices.append(f"回复用了本地兜底（{reply.notice}）")
    st.session_state["notice"] = ""
    st.session_state["last_notice"] = "；".join(notices)


def render_settings() -> None:
    """开局设置：选游戏、选陪伴模式、今日游戏状态。"""
    state: GameState = st.session_state["game_state"]
    persona_option = st.session_state.get("persona_choice") or DEFAULT_PERSONA

    with st.container(border=True):
        st.markdown('<div class="gb-section">开局设置</div>', unsafe_allow_html=True)

        col_game, col_persona = st.columns(2, gap="large")
        with col_game:
            st.caption("选择游戏")
            st.segmented_control(
                "选择游戏",
                GAME_OPTIONS,
                key="game_choice",
                label_visibility="collapsed",
            )
        with col_persona:
            st.caption("陪伴模式")
            st.segmented_control(
                "陪伴模式",
                PERSONA_OPTIONS,
                key="persona_choice",
                label_visibility="collapsed",
            )

        st.divider()

        st.markdown('<div class="gb-section">今日游戏状态</div>', unsafe_allow_html=True)
        col_plays, col_wins, col_losses = st.columns(3)
        col_plays.metric("对局", state.plays)
        col_wins.metric("胜利", state.wins)
        col_losses.metric("失败", state.losses)

        shown_persona = persona_key_from_option(persona_option) or state.persona
        st.caption(f"当前状态：{state.mood}　·　陪伴模式：{persona_title(shown_persona)}")

        col_win, col_loss, col_reset, col_clear = st.columns(4)
        with col_win:
            st.button("+ 胜利", key="btn_win", on_click=add_win, use_container_width=True)
        with col_loss:
            st.button("+ 失败", key="btn_loss", on_click=add_loss, use_container_width=True)
        with col_reset:
            st.button("重置今日状态", key="btn_reset", on_click=reset_today, use_container_width=True)
        with col_clear:
            st.button("清空对话", key="btn_clear", on_click=clear_chat, use_container_width=True)


def render_input() -> None:
    """输入区：输入框、开始陪伴、快速体验。"""
    with st.container(border=True):
        st.markdown('<div class="gb-section">你想说的话</div>', unsafe_allow_html=True)
        st.text_area(
            "告诉你的游戏搭子发生了什么",
            key="user_input",
            height=150,
            placeholder="例如：三连跪了，队友一直送，我真的烦死了",
            label_visibility="collapsed",
        )
        st.button("开始陪伴", key="submit", type="primary", use_container_width=True, on_click=queue_submit)

        st.caption("快速体验")
        for chunk in (QUICK_PROMPTS[:2], QUICK_PROMPTS[2:]):
            columns = st.columns(2)
            for column, prompt in zip(columns, chunk):
                with column:
                    st.button(
                        prompt,
                        key=f"quick_{prompt}",
                        on_click=fill_input,
                        args=(prompt,),
                        use_container_width=True,
                    )


def split_turns(turns: list[dict[str, str]]) -> tuple[str, str, list[dict[str, str]]]:
    """拆出最近一轮的用户输入、AI 回复和更早的历史。"""
    last_user = ""
    last_reply = ""
    for turn in reversed(turns):
        if turn["role"] == "assistant" and not last_reply:
            last_reply = turn["content"]
        elif turn["role"] == "user" and not last_user:
            last_user = turn["content"]

    history = turns[:-2] if len(turns) >= 2 else []
    return last_user, last_reply, history


def render_reply() -> None:
    """回复区：搭子的回应、状态分析、反馈、历史对话。"""
    memory: Memory = st.session_state["memory"]
    last_user, last_reply, history = split_turns(memory.turns)

    st.markdown('<div class="gb-section">搭子的回应</div>', unsafe_allow_html=True)

    if not last_reply:
        with st.container(border=True):
            st.write("还没有开场。在上面说说今天打游戏发生了什么，也可以直接点一个快速体验的例子。")
        return

    with st.container(border=True):
        if last_user:
            st.markdown(f'<div class="gb-said">你说：{last_user}</div>', unsafe_allow_html=True)
        st.markdown(last_reply)

    if st.session_state["last_notice"]:
        st.warning(f"这一轮 AI 没有完全跑通：{st.session_state['last_notice']}")

    render_analysis()

    col_up, col_down, _ = st.columns([1, 1, 2])
    with col_up:
        st.button("👍 有用", key="fb_up", on_click=set_feedback, args=("up",), use_container_width=True)
    with col_down:
        st.button("👎 没感觉", key="fb_down", on_click=set_feedback, args=("down",), use_container_width=True)
    if memory.last_feedback == "up":
        st.caption("已记录：这轮回复有用，下一轮保持这个方向。")
    elif memory.last_feedback == "down":
        st.caption("已记录：这轮没什么感觉，下一轮我会说得更具体。")

    if history:
        with st.expander("更早的对话"):
            for turn in history:
                who = "你" if turn["role"] == "user" else "搭子"
                st.markdown(f"**{who}**：{turn['content']}")


def render_analysis() -> None:
    """AI 状态分析卡片。"""
    analysis = st.session_state["memory"].last_analysis
    if not analysis:
        return
    with st.expander("AI 状态分析", expanded=True):
        chips = [
            ("游戏", analysis["game"]),
            ("场景", analysis["scene"]),
            ("情绪", analysis["emotion"]),
            ("意图", analysis["intent"]),
            ("策略", analysis["strategy"]),
            ("人格", persona_title(analysis["persona"])),
        ]
        st.markdown(
            "".join(f'<span class="gb-chip">{name}：{value}</span>' for name, value in chips),
            unsafe_allow_html=True,
        )
        if analysis.get("source") == "fallback":
            st.caption("这一轮的分析来自本地兜底规则。")


def main() -> None:
    init_session()

    st.markdown('<div class="gb-hero-title">🎮 GameBuddy</div>', unsafe_allow_html=True)
    st.markdown('<div class="gb-hero-sub">你的 AI 游戏搭子，不只是聊天机器人。</div>', unsafe_allow_html=True)

    if not has_api_key():
        st.warning(f"还没有配置可用的 API Key，现在只能用本地兜底规则。{ENV_HINT}")
    if st.session_state["notice"]:
        st.error(st.session_state["notice"])

    game = st.session_state.get("game_choice") or DEFAULT_GAME
    persona_option = st.session_state.get("persona_choice") or DEFAULT_PERSONA
    st.session_state["game_state"].game = game

    pending = st.session_state.pop("pending_submit", "")
    if pending:
        handle_submit(pending, game, persona_option)

    render_settings()
    st.write("")
    render_input()
    st.write("")
    render_reply()


main()