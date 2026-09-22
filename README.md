# GameBuddy｜AI 游戏陪伴 Agent

一个可以现场演示的 AI 产品 Demo：它不是一个普通聊天机器人，而是先理解玩家在打什么游戏、处于什么场景和情绪，再决定用哪种陪伴策略和人格回应的「AI 游戏搭子」。

## 项目介绍

玩家在游戏里遇到的往往不是"问题"，而是一段情绪和处境：连跪、卡关、被队友影响、赢了想分享、晚上不知道玩什么。GameBuddy 把这些先分析清楚，再生成符合场景和人格的回复，并用上下文记住之前聊过什么。

## 功能介绍

- 场景理解：识别 game / scene / emotion / intent / strategy 五个维度
- 四种人格：🐱 温柔搭子、😈 损友搭子、🎮 游戏教练、🧙 冒险搭子
- 人格自动选择：选「✨ AI 自动选择」时，Agent 根据游戏、场景、情绪、意图自己挑人格
- 上下文记忆：session_state 保存最近 10 条对话，能接住"我马上掉星了"这类延续话题
- 今日游戏状态：手动记录今日对局、胜负，Agent 回复时会参考
- 用户反馈：👍 有用 / 👎 没感觉，会作为下一轮 Prompt 的输入
- 快速体验：四个 Demo 场景一键填入
- 兜底能力：API 不可用时用本地规则和回复，页面依然可用

## 技术栈

- Python 3.10+
- Streamlit（前端）
- OpenAI Python SDK（DeepSeek 等 OpenAI 兼容接口）
- python-dotenv（管理 API Key）
- 不使用数据库、RAG、复杂 Agent 框架

## 项目结构

```
gamebuddy/
├── app.py                        # Streamlit 页面与流程编排
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
├── core/
│   ├── analyzer.py               # 场景/情绪/意图/策略分析 + 人格决策 + 兜底
│   ├── companion.py              # 按人格生成回复 + 兜底回复
│   ├── memory.py                 # 对话记忆（最近 10 条、最近分析与反馈）
│   └── game_state.py             # 今日游戏状态（对局、胜负、状态、人格）
└── prompts/
    ├── analyzer_prompt.py        # 分析提示词与枚举值
    └── companion_prompt.py       # 四种人格、策略提示、回复规则
```

## 安装方法

```bash
cd gamebuddy
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## API Key 配置

```bash
# Windows
copy .env.example .env
# macOS / Linux
cp .env.example .env
```

然后编辑 `.env`：

```
OPENAI_API_KEY=你的DeepSeekKey
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat
```

- DeepSeek Key 在 platform.deepseek.com 的 API keys 页面创建，`sk-` 开头。
- 换成官方 OpenAI 时把 `OPENAI_BASE_URL` 留空，`OPENAI_MODEL` 改成 `gpt-4o-mini`。
- `.env` 已被 `.gitignore` 忽略，不要提交。

## 启动方法

```bash
streamlit run app.py
```

浏览器打开 `http://localhost:8501`，终端窗口要保持开着。

## Demo 使用示例

| 输入 | 预期理解 |
| --- | --- |
| 三连跪了，队友一直送，我真的烦死了 | 连败 / 烦躁 / 倾诉 / 情绪安抚 |
| 终于上王者了，打了一晚上终于成功了 | 获胜 / 兴奋 / 分享喜悦 / 分享喜悦 |
| 双人成行这个地方卡了半个小时了，完全不知道怎么过 | 卡关 / 挫败 / 寻求攻略 / 游戏指导 |
| 今天晚上想玩点游戏 | 想聊天 / 平静 / 寻求聊天 / 主动聊天 |

上下文记忆演示：连续发送「王者三连跪了」→「我马上掉星了」→「算了不打了」，第三句应该能接住前两轮的连败和掉星语境，而不是重新开始。

## 后续可以扩展的功能

1. 接入真实战绩数据，替代手动点 + 胜利 / + 失败
2. 把 👍/👎 反馈落库，统计哪种人格和策略效果最好
3. 引入 RAG，接入版本、机制、攻略资料，让游戏建议更准确
4. 多轮长记忆：把用户长期偏好（常玩游戏、雷点、称呼）存下来
5. 语音输入输出，做成真正"开黑搭子"的形态
6. 人格自定义与自定义开场白