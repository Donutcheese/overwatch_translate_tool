"""短语缓存与行级记忆单元测试（无 UI / 无网络）。"""

from __future__ import annotations

from ow_color_fluent.services.phrase_cache import (
    OW_PHRASE_DICT,
    TranslationMemory,
    normalize_chat_text,
)


def test_normalize_and_dict_hit() -> None:
    assert normalize_chat_text("  C9  ") == "c9"
    assert OW_PHRASE_DICT[normalize_chat_text("힐좀")] == "奶一下"
    mem = TranslationMemory(max_entries=8)
    assert mem.lookup("group up") == "集合"
    assert mem.lookup("support diff") == "辅助差距"


def test_line_memory_lru() -> None:
    mem = TranslationMemory(max_entries=64)
    mem.store("genji blade mid", "源氏中路拔刀")
    assert mem.lookup("Genji Blade Mid") == "源氏中路拔刀"
    mem.store("  genji blade mid ", "源氏中路开大")
    assert mem.lookup("genji blade mid") == "源氏中路开大"


if __name__ == "__main__":
    test_normalize_and_dict_hit()
    test_line_memory_lru()
    print("phrase_cache ok")
