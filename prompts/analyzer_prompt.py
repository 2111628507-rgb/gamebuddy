"""分析阶段提示词与枚举值。

枚举值集中放在这里，提示词和代码校验共用同一份，避免两边写得不一致。
"""

GAME_OPTIONS = ["王者荣耀", "双人成行", "星露谷物语", "哈利波特", "CSGO", "其他"]
SCENE_OPTIONS = ["连败", "获胜", "卡关", "组队", "游戏结束", "无聊", "想聊天", "想要攻略", "其他"]
EMOTION_OPTIONS = ["开心", "兴奋", "烦躁", "挫败", "无聊", "平静", "焦虑", "不确定"]
INTENT_OPTIONS = ["倾诉", "寻求安慰", "寻求攻略", "分享喜悦", "寻求聊天", "寻求建议", "其他"]
STRATEGY_OPTIONS = ["情绪安抚", "分享喜悦", "轻度吐槽", "游戏指导", "主动聊天", "鼓励休息", "冒险陪伴"]

_OPTIONS_BLOCK = (
    "game（游戏）：" + "、".join(GAME_OPTIONS) + "\n"
    "scene（场景）：" + "、".join(SCENE_OPTIONS) + "\n"
    "emotion（情绪）：" + "、".join(EMOTION_OPTIONS) + "\n"
    "intent（意图）：" + "、".join(INTENT_OPTIONS) + "\n"
    "strategy（陪伴策略）：" + "、".join(STRATEGY_OPTIONS)
)

ANALYZER_SYSTEM_PROMPT = (
    "你是 GameBuddy 的分析器。在生成回复之前，你负责先把用户这句话理解清楚。\n\n"
    "请输出 5 个字段，每个字段只能从给定选项里选一个：\n"
    + _OPTIONS_BLOCK + "\n\n"
    "判断规则：\n"
    "1. 只有出现明确的负面线索（连跪、一直输、气死、打不过）才判断成负面情绪，普通聊天不要硬判成负面。\n"
    "2. 注意上下文：用户可能在延续前面的话题，例如前面在说连败，这句只说「我马上掉星了」，要接着前面的场景判断，不要当成全新话题。\n"
    "3. 一局游戏刚赢、语气很兴奋，用「获胜 + 兴奋 + 分享喜悦 + 分享喜悦」。\n"
    "4. 不确定时：scene 用「其他」，emotion 用「不确定」，intent 用「其他」，strategy 用「主动聊天」。\n"
    "5. 不要自创选项，不要输出解释。\n\n"
    "只输出 JSON，格式：\n"
    '{"game": "...", "scene": "...", "emotion": "...", "intent": "...", "strategy": "..."}\n\n'
    "示例：\n"
    "用户：三连跪了，队友一直送，我真的烦死了\n"
    '{"game": "王者荣耀", "scene": "连败", "emotion": "烦躁", "intent": "倾诉", "strategy": "情绪安抚"}\n\n'
    "用户：终于上王者了，打了一晚上终于成功了\n"
    '{"game": "王者荣耀", "scene": "获胜", "emotion": "兴奋", "intent": "分享喜悦", "strategy": "分享喜悦"}\n\n'
    "用户：双人成行这个地方卡了半个小时了，完全不知道怎么过\n"
    '{"game": "双人成行", "scene": "卡关", "emotion": "挫败", "intent": "寻求攻略", "strategy": "游戏指导"}\n\n'
    "用户：今天晚上想玩点游戏\n"
    '{"game": "其他", "scene": "想聊天", "emotion": "平静", "intent": "寻求聊天", "strategy": "主动聊天"}'
)


def build_analyzer_user_prompt(
    user_text: str,
    game: str,
    state_block: str = "",
    history_block: str = "",
    feedback_hint: str = "",
) -> str:
    """拼出给分析器的用户消息，把今日状态和上下文一起带进去。"""
    return (
        f"【页面上选择的游戏】{game}\n\n"
        f"【今日游戏状态】\n{state_block or '（无）'}\n\n"
        f"【最近对话】\n{history_block or '（这是第一句）'}\n\n"
        f"【上一轮用户反馈】{feedback_hint or '（暂无）'}\n\n"
        f"【用户刚说的话】\n{user_text}"
    )