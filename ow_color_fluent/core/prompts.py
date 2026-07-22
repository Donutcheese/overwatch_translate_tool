"""Prompt 配置：多通道 OCR + 颜色语义保真翻译。"""

from __future__ import annotations

import json
from typing import Iterable, Optional

from .config import OCRResult

# ---------------------------------------------------------------------------
# GLM-OCR：OW 专用基础 Prompt + 分通道 Hint
# ---------------------------------------------------------------------------
GLM_OCR_BASE_PROMPT: str = """\
这是《守望先锋》(Overwatch) 游戏内聊天截图，经颜色掩码预处理后的二值图（白底黑字或反色高对比）。

请识别图中全部可见文字，内容可能为韩语、日语、英语、中文或混排。
常见形式：短句、英雄名/缩写（Genji、Ana、Rein）、数字+hp（1hp）、C9、diff、ult、focus、touch 等竞技 callout。
语气可能是友好协作，也可能是嘲讽、辱骂或阴阳怪气——均需如实识别原文，不要过滤、不要改写。

输出规则（严格遵守）：
1. 按从上到下、从左到右的阅读顺序输出。
2. 每行一条独立消息；同一行内连续文字不要拆行。
3. 只输出识别到的原文，保留原文语言，不要翻译。
4. 不要解释、不要 Markdown、不要引号包裹、不要「识别结果：」等前后缀。
5. 看不清或无法确定的字符用 ? 代替，不要编造。
6. 若该通道实际上没有文字，输出空内容，不要臆造。"""

GLM_OCR_CHANNEL_HINTS: dict[str, str] = {
    "Enemy": (
        "【通道：Enemy / 红色】在 OW 聊天中，该颜色通道基本不会出现可读聊天文字"
        "（多为敌方标识色，正常对局几乎无红色字聊天）。"
        "若无清晰文字，请直接输出空；切勿把噪点、UI 残影或名字条误识别为聊天内容。"
    ),
    "Friendly": (
        "【通道：Friendly / 蓝色】同局友方（非组队频道）玩家发言。"
        "内容可能是友好协作（报点、求奶、报 CD），也可能是嘲讽、辱骂、阴阳怪气或恶意甩锅——"
        "无论正负情绪，均按原文逐字识别，不要省略攻击性用语。"
    ),
    "Group": (
        "【通道：Group / 绿色】组队/小队频道发言。"
        "可能是战术配合与鼓励，也可能是抱怨、互喷或消极言论——均需完整识别原文，不过滤、不美化。"
    ),
    "Alert": (
        "【通道：Alert / 橙色】全体玩家可见的通告/提醒类文字（非某一队私聊）。"
        "常见：匹配状态、倒计时、胜负/占点提示、赞赏/留榜、机制说明、活动通知等。"
        "文本可能偏短、含数字或英文专有名词；不要漏掉数字、符号与英文缩写。"
    ),
}

# 向后兼容：未指定通道时使用基础 Prompt
GLM_OCR_USER_PROMPT: str = GLM_OCR_BASE_PROMPT

DEEPSEEK_SYSTEM_PROMPT: str = """\
你是《守望先锋》(Overwatch 2) 亚服资深玩家兼实时聊天本地化翻译器，精通中/英/韩/日游戏俚语、缩写与 callout（如 C9、1hp、diff、ult、touch、nano、blade、beat、lamp、suzu）。

OCR 已按聊天语义颜色分通道预处理：
- Enemy（红）：OW 聊天中几乎不会出现红色文字；若 OCR 仍给出内容，按原文翻译，但勿臆造。
- Friendly（蓝）：同局友方频道。
- Group（绿）：组队频道。
- Alert（橙）：全体玩家可见的通告/提醒（匹配、倒计时、胜负、赞赏、机制提示等），不是某一队私聊。

## 翻译任务
将 KR/JP/EN（及混排）游戏聊天或 Alert 通告，本地化为中国大陆 FPS 玩家习惯的中文。
友好协作与恶意嘲讽/辱骂/阴阳怪气均需翻译，不得因负面情绪而跳过、省略或替换成「[已过滤]」。
脏话与攻击语：保留竞技局语境，用国服常见口语意译（可适度弱化极端脏字，但须保留原意与情绪强度）。

## 输出规则（绝对遵守）
1. 严格 JSON 数组，每项：{"color_tag":"<Enemy|Friendly|Group|Alert>","source_text":"<原文>","translated":"<中文>"}。
2. 只输出 JSON，不要 Markdown、不要解释、不要「翻译如下」等 filler。
3. color_tag 必须与输入 OCR 块一致；source_text 尽量回传输入原文便于对齐。
4. 已是中文的内容可微调润色；纯数字/符号可原样或最小润色。
5. Alert 通道的全体可见通告同样必须完整本地化。
6. 输出要短：每条 translated 尽量 ≤ 24 个汉字，像局内字幕。

## 术语与风格
- 英雄名、大招、竞技 callout 使用国服/简中玩家通行叫法：Genji=源氏，Rein=大锤，Hog=猪，Cass=麦克雷/卡西迪，Soldier=76，Lucio=卢西奥，Mercy=天使，Moira=莫伊拉，Winston=猩猩，D.Va=DVA，Ball=球，Widow=黑百合，Hanzo=半藏，Zen=和尚，Brig=锤妹，Kiri=雾子，Juno=朱诺。
- 常见 callout 本地化：1hp/one=一丝，low=残，no heal=没奶，anti/purple=禁疗/紫了，sleep=睡了，stun=晕了，discord=挂球，rez=复活，lamp=灯，suzu=铃，beat=音障，nano=激素，blade=拔刀，visor=开瞄，shatter=裂地猛击，grav=吸，flux=引力乱流，touch=踩点/摸点，contest=续点，C9=没踩点，diff=差距/被爆，swap=换人，feed=送，throw=摆/演。
- 语言要短、快、像局内字幕；不要翻成书面语、客服腔或机器腔。
- 禁止编造不存在的技能名或玩家未说的内容。"""


def build_ocr_user_prompt(color_label: Optional[str] = None) -> str:
    """按颜色通道组装 OCR 用户 Prompt。"""
    hint = GLM_OCR_CHANNEL_HINTS.get(color_label or "", "")
    if not hint:
        return GLM_OCR_BASE_PROMPT
    return f"{GLM_OCR_BASE_PROMPT}\n\n{hint}"


def build_translation_messages(ocr_results: Iterable[OCRResult]) -> list[dict[str, str]]:
    """构造带颜色语义的翻译消息体。

    注意：system 段必须保持字节级稳定，才能命中 DeepSeek 磁盘 Context Cache，
    降低 TTFT；可变 OCR 内容只能放在末尾 user 消息。
    """
    payload: list[dict[str, str]] = []
    for item in ocr_results:
        if not item.is_valid or not item.raw_text.strip():
            continue
        payload.append(
            {
                "color_tag": item.color_tag.label if item.color_tag else "Unknown",
                "raw_text": item.raw_text.strip(),
            }
        )

    return [
        {"role": "system", "content": DEEPSEEK_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "将以下 OCR 文本块本地化为中文游戏术语。"
                "友好与恶意/嘲讽内容均需翻译，保留 color_tag 与 source_text。"
                "严格按 System Prompt 输出 JSON 数组，"
                '每项含 color_tag/translated，并尽量带回 source_text：\n'
                + json.dumps(payload, ensure_ascii=False)
            ),
        },
    ]


def build_warmup_messages() -> list[dict[str, str]]:
    """启动时预热指令前缀：与真实翻译请求共享同一 system 前缀。"""
    return [
        {"role": "system", "content": DEEPSEEK_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "将以下 OCR 文本块本地化为中文游戏术语。"
                "友好与恶意/嘲讽内容均需翻译，保留 color_tag 与 source_text。"
                "严格按 System Prompt 输出 JSON 数组，"
                '每项含 color_tag/translated，并尽量带回 source_text：\n'
                + json.dumps(
                    [{"color_tag": "Friendly", "raw_text": "group up"}],
                    ensure_ascii=False,
                )
            ),
        },
    ]


def build_ocr_messages(
    base64_png: str, *, color_label: Optional[str] = None
) -> list[dict]:
    """构造 GLM-OCR 多模态消息体；可按颜色通道注入专用 Hint。"""
    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{base64_png}"},
                },
                {"type": "text", "text": build_ocr_user_prompt(color_label)},
            ],
        }
    ]
