"""本地俚语词典 + 行级翻译缓存：热路径跳过 LLM。"""

from __future__ import annotations

import re
from collections import OrderedDict
from typing import Optional


def normalize_chat_text(text: str) -> str:
    """归一化聊天文本，提高缓存命中率。"""
    cleaned = text.strip().lower()
    cleaned = cleaned.replace("＠", "@").replace("！", "!").replace("？", "?")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


# OW 亚服高频短句/callout → 国服口语（可继续扩充）
OW_PHRASE_DICT: dict[str, str] = {
    "c9": "没踩点",
    "diff": "差距",
    "support diff": "辅助差距",
    "dps diff": "输出差距",
    "tank diff": "坦克差距",
    "1hp": "一丝血",
    "one hp": "一丝血",
    "low": "残血",
    "no heal": "没奶",
    "no ult": "没大",
    "group up": "集合",
    "group": "集合",
    "push": "推进",
    "fall back": "撤",
    "focus": "集火",
    "swap": "换人",
    "feed": "送",
    "throw": "摆",
    "throwing": "在摆",
    "touch": "踩点",
    "contest": "续点",
    "anti": "禁疗",
    "purple": "紫了",
    "sleep": "睡了",
    "nano": "激素",
    "blade": "拔刀",
    "beat": "音障",
    "lamp": "灯",
    "suzu": "铃",
    "shatter": "裂地",
    "grav": "吸",
    "visor": "开瞄",
    "rez": "复活",
    "discord": "挂球",
    "heal me": "奶我",
    "need heal": "要奶",
    "gg": "GG",
    "wp": "打得好",
    "glhf": "好运玩得开心",
    "afk": "挂机",
    "보고": "汇报",
    "힐좀": "奶一下",
    "힐 좀": "奶一下",
    "힐좀요": "奶一下啊",
    "힐": "奶",
    "궁": "大招",
    "궁있다": "有大",
    "궁없어": "没大",
    "집결": "集合",
    "모여": "集合",
    "밀어": "推",
    "빼": "撤",
    "점령": "占点",
    "터치": "踩点",
    "디프": "差距",
    "쓰레기": "垃圾",
    "ㅅㅂ": "靠",
    "ㅂㅅ": "白痴",
    "ㅋㅋ": "哈哈",
    "ㅎㅎ": "呵呵",
    "ㅇㅇ": "嗯",
    "ㄴㄴ": "不行",
    "ㄱㄱ": "冲",
    "ㅈㄱ": "稍等",
}


class TranslationMemory:
    """LRU 行级翻译记忆 + 俚语词典。"""

    def __init__(self, *, max_entries: int = 512) -> None:
        self._max_entries = max(64, max_entries)
        self._line_cache: OrderedDict[str, str] = OrderedDict()

    def lookup(self, raw_text: str) -> Optional[str]:
        key = normalize_chat_text(raw_text)
        if not key:
            return None

        phrase = OW_PHRASE_DICT.get(key)
        if phrase is not None:
            return phrase

        cached = self._line_cache.get(key)
        if cached is not None:
            self._line_cache.move_to_end(key)
            return cached
        return None

    def store(self, raw_text: str, translated: str) -> None:
        key = normalize_chat_text(raw_text)
        text = translated.strip()
        if not key or not text:
            return
        if key in OW_PHRASE_DICT:
            return
        if key in self._line_cache:
            self._line_cache.move_to_end(key)
            self._line_cache[key] = text
            return
        self._line_cache[key] = text
        while len(self._line_cache) > self._max_entries:
            self._line_cache.popitem(last=False)

    def clear(self) -> None:
        self._line_cache.clear()


# 进程级共享记忆，跨多次 F8 命中
GLOBAL_TRANSLATION_MEMORY = TranslationMemory()
