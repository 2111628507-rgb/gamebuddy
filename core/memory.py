"""对话记忆模块。

第一版只用 session_state 存在内存里，不落库；保留最近 10 条对话和最近一次分析、反馈。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MAX_TURNS = 10


@dataclass
class Memory:
    """一次会话内的上下文记忆。"""

    turns: list[dict[str, str]] = field(default_factory=list)
    last_analysis: dict[str, Any] | None = None
    last_feedback: str = ""      # "" / "up" / "down"
    last_user_text: str = ""

    def add_user(self, text: str) -> None:
        """记录用户这一句。"""
        self.turns.append({"role": "user", "content": text})
        self.last_user_text = text
        self._trim()

    def add_assistant(self, text: str) -> None:
        """记录 AI 这一句。"""
        self.turns.append({"role": "assistant", "content": text})
        self._trim()

    def set_analysis(self, analysis) -> None:
        """保存最近一次分析结果，用于页面展示和分析来源标记。"""
        self.last_analysis = analysis.to_dict() if hasattr(analysis, "to_dict") else dict(analysis)

    def set_feedback(self, value: str) -> None:
        """保存用户对最近一条回复的反馈。"""
        self.last_feedback = value

    def recent(self, limit: int = MAX_TURNS) -> list[dict[str, str]]:
        """最近若干条对话。"""
        return self.turns[-limit:]

    def recent_text(self, limit: int = 6) -> str:
        """把最近几轮压成一段纯文本，作为分析器和回复模型的上下文。"""
        lines = [
            f"{'用户' if turn['role'] == 'user' else 'AI'}：{turn['content']}"
            for turn in self.turns[-limit:]
        ]
        return "\n".join(lines)

    def feedback_hint(self) -> str:
        """把上一轮反馈翻译成给模型的提示。"""
        if self.last_feedback == "up":
            return "用户觉得上一轮回复有用，保持这种风格。"
        if self.last_feedback == "down":
            return "用户觉得上一轮回复没什么感觉，这一轮减少空泛安慰，给更具体的内容。"
        return ""

    def reset(self) -> None:
        """清空本轮会话的记忆。"""
        self.turns.clear()
        self.last_analysis = None
        self.last_feedback = ""
        self.last_user_text = ""

    def _trim(self) -> None:
        if len(self.turns) > MAX_TURNS:
            del self.turns[:-MAX_TURNS]