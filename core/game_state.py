"""今日游戏状态。

第一版由用户手动维护（点按钮加胜负），Agent 回复时会参考这份状态。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GameState:
    """今天这个游戏的整体情况。"""

    game: str = "王者荣耀"
    plays: int = 0
    wins: int = 0
    losses: int = 0
    mood: str = "平静"
    persona: str = "温柔搭子"

    def add_win(self) -> None:
        """记一把胜利。"""
        self.wins += 1
        self.plays += 1

    def add_loss(self) -> None:
        """记一把失败。"""
        self.losses += 1
        self.plays += 1

    def reset(self) -> None:
        """重置今日战绩。"""
        self.plays = 0
        self.wins = 0
        self.losses = 0
        self.mood = "平静"

    def summary(self) -> str:
        """给页面用的一句话总结。"""
        if self.plays == 0:
            return "今天还没有开局记录。"
        return f"今天打了 {self.plays} 把，{self.wins} 胜 {self.losses} 负。"

    def as_prompt_block(self) -> str:
        """拼成给模型看的今日状态。"""
        return (
            f"游戏：{self.game}\n"
            f"今日对局：{self.plays}\n"
            f"胜利：{self.wins}\n"
            f"失败：{self.losses}\n"
            f"当前状态：{self.mood}\n"
            f"陪伴模式：{self.persona}"
        )