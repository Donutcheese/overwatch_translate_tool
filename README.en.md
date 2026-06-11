# OW-Light-Translator

> Lightweight · Real-time · Anti-cheat-friendly · Overwatch screen translation overlay

**Language / 语言 / 言語 / 언어：** [中文](README.md) | **English** | [日本語](README.ja.md) | [한국어](README.ko.md)

---

## English

### Introduction

**OW-Light-Translator** is an **external screen-translation tool** for *Overwatch* players. When Asian-server chat mixes Korean, Japanese, and English—`힐좀`, `C9`, `support diff`, `genji 1hp`—you select a region, trigger capture with one hotkey, and get **mainland-Chinese gamer terminology** on a transparent overlay without interrupting gameplay.

Built for:

- Competitive players on Asian servers who need fast comms translation
- Python developers learning **external overlay + async OCR/LLM** architecture

### Anti-cheat & safety

This tool performs **zero memory read/write**, **zero DLL injection**, and **zero simulated input**. It only uses standard Windows desktop capture (`mss` / Desktop Duplication) and renders results in an external window—similar in approach to OBS or Discord overlay.

> ⚠️ Use at your own risk. Not affiliated with Blizzard Entertainment. No guarantee regarding anti-cheat compatibility—please proceed with caution.

### OCR recognition

OCR currently relies on **default settings**: multi-channel masking based on four Overwatch chat semantic colors (Enemy / Friendly / Group / Alert). Color ranges are defined in `COLOR_PALETTE` inside `config.py`.

<p align="center">
  <img src="img/font_color.png" alt="Overwatch chat font color semantics" width="720">
</p>

> Above: in-game chat text colors mapped to semantic tags. Enemy (red), Friendly (blue), Group (green), Alert (orange).

### Key features

| Feature | Description |
|---------|-------------|
| Dual UI modes | **Edit mode**: draggable, resizable capture region; **Locked mode**: frameless, transparent, click-through, always on top |
| Zero disk I/O | Screenshots converted to Base64 in memory—no temp files |
| Multi-channel OCR | Color-masked channels reduce background noise during recognition |
| Async pipeline | Non-blocking UI and hotkeys; capture → OCR → translate on background `asyncio` workers |
| OW slang expert | Built-in DeepSeek System Prompt covering C9, Diff, hero shorthand, and common KR/JP callouts |

### Workflow

<p align="center">
  <img src="img/image.png" alt="OW-Light-Translator detailed system flowchart" width="900">
</p>

> Above: full pipeline — `mss` region capture (in-memory Base64) → `COLOR_PALETTE` multi-channel masking → Zhipu GLM-OCR → DeepSeek localization → CustomTkinter overlay with semantic color rendering.

### Project structure

```
overwatch_translate_tool/
├── main.py                  # Entry point (calls ow_color_fluent.app.main)
├── ow_color_fluent/         # Main package (UI, API, runtime)
├── api_client.py            # Compatibility re-exports
├── config.py                # Compatibility re-exports
├── prompts.py               # Compatibility re-exports
├── local_api_keys.py        # Local API keys (gitignored)
├── requirements.txt         # Full Windows deps (UI included)
├── requirements-docker.txt    # Docker API-only deps
├── Dockerfile / docker-compose.yml
├── DOCKER_README.md
├── img/
│   ├── image.png      # Detailed system flowchart
│   └── font_color.png # Chat color semantics reference
├── requirements.txt
├── README.md
├── README.en.md
├── README.ja.md
└── README.ko.md
```

### Developer guide

For contributors: environment setup, tech stack, and collaboration workflow.

#### Requirements

| Category | Requirement | Notes |
|----------|-------------|-------|
| OS | **Windows 10/11** | Primary target; `mss` capture and `keyboard` hotkeys work best on Windows |
| Python | **3.10+** (3.11 / 3.12 recommended) | Uses modern `dataclass(slots=True)` syntax |
| Packages | `pip` + `venv` | Virtual environment strongly recommended |
| VCS | **Git** | Fork → branch → PR workflow |
| IDE | **VS Code / Cursor** | Python + Pylance extensions; dual monitor helps for overlay debugging |
| Optional | *Overwatch* client | Needed for in-game capture/OCR tuning; API-only work does not require the game |

#### Tech stack

| Layer | Library / Service | Version | Role in this project |
|-------|-------------------|---------|----------------------|
| UI | [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) | `>=5.2.2` | Frameless transparent overlay, drag/resize, color-coded text |
| Windows API | [pywin32](https://github.com/mhammond/pywin32) | `>=306` | DPI awareness, mouse click-through (`WS_EX_TRANSPARENT`) |
| Capture | [mss](https://python-mss.readthedocs.io/) | `>=9.0.1` | Region desktop capture, in-memory only |
| Image | [OpenCV](https://opencv.org/) | `>=4.10` | Color masking (`inRange`), morphology, in-memory PNG encode |
| Numeric | [NumPy](https://numpy.org/) | `>=1.26` | Frame and mask array operations |
| Network | [httpx](https://www.python-httpx.org/) | `>=0.27` | Async HTTP to GLM-OCR and DeepSeek |
| Concurrency | `asyncio` (stdlib) | — | Decouple UI thread from OCR/translation workers |
| Hotkeys | [keyboard](https://github.com/boppreh/keyboard) | `>=0.13.5` | Global shortcuts (capture, lock toggle) |
| Config | [python-dotenv](https://github.com/theskumar/python-dotenv) | `>=1.0` | Optional `.env` for URLs, timeouts |
| OCR API | Zhipu **GLM-OCR** (`glm-ocr`) | — | Multi-channel masked text recognition |
| Translation API | **DeepSeek Chat** (`deepseek-chat`) | — | OW KR/JP/EN slang → Chinese gamer terms |

#### Quick start

```bash
git clone https://github.com/<your-org>/overwatch_translate_tool.git
cd overwatch_translate_tool

python -m venv venv
venv\Scripts\Activate.ps1          # Windows PowerShell

pip install -U pip
pip install -r requirements.txt

# Or use setup script:
# .\scripts\setup_venv.bat

# Configure API keys (see below), then:
python main.py
```

> **Note:** The `venv/` folder is gitignored. Run `scripts/setup_venv.ps1` or `.bat` locally — do not commit the virtual environment.

Default hotkeys: `F8` capture/OCR, `F9` toggle lock/click-through (override via `HOTKEY_CAPTURE` / `HOTKEY_TOGGLE_LOCK`). Run PowerShell as **admin** if global hotkeys fail.

#### API keys

Edit `local_api_keys.py` at repo root (gitignored):

```python
GLM_API_KEY = "your Zhipu GLM key"
DEEPSEEK_API_KEY = "your DeepSeek key"
```

Fallback via `.env` (priority: `local_api_keys.py` > env vars):

```env
GLM_API_KEY=...
DEEPSEEK_API_KEY=...
HTTP_TIMEOUT_SEC=30
```

#### Module map (where to edit)

| File | Responsibility | Typical changes |
|------|----------------|-----------------|
| `config.py` | DTOs, `COLOR_PALETTE`, API endpoints | Chat color mask ranges, timeouts |
| `prompts.py` | OCR/translation prompts, message builders | OW slang, translation tone |
| `api_client.py` | Capture, masking, OCR/translation HTTP | Concurrency, retries, parsing |
| `ow_color_fluent/ui/overlay_window.py` | CustomTkinter overlay | Multi-resolution layout, click-through, rendering |
| `ow_color_fluent/app.py` | App entry + `mainloop()` | Startup flow |
| `main.py` | CLI entry | Usually unchanged |
| `local_api_keys.py` | Local secrets | Machine-only, never commit |
| `img/font_color.png` | Color semantics reference | Update when OW chat colors change |

#### Contribution workflow

```
Fork repo
   │
   ▼
git checkout -b feat/your-feature
   │
   ▼
Code + local validation
   │
   ▼
git commit / git push → open Pull Request
```

**PR checklist:** motivation, affected modules, how you tested (API-only vs in-game).

#### Local debugging

**API layer (no game):**

```python
import asyncio
from api_client import capture_region_to_base64, process_multi_channel_ocr, translate_ocr_results

async def smoke_test():
    capture = capture_region_to_base64({"left": 0, "top": 0, "width": 800, "height": 400})
    ocr = await process_multi_channel_ocr(capture)
    trans = await translate_ocr_results(ocr)
    print(trans)

asyncio.run(smoke_test())
```

**Full overlay (Windows + game):** run `python main.py`, select chat region, trigger capture hotkey.

| Symptom | Check |
|---------|-------|
| Empty OCR | `GLM_API_KEY`, `COLOR_PALETTE`, capture region |
| Empty translation | `DEEPSEEK_API_KEY`, network/proxy, `prompts.py` output |
| Hotkeys dead | Run as admin on Windows if needed, shortcut conflicts |
| Import errors | venv activated, `pip install -r requirements.txt` |

### Development status

| Module | Status |
|--------|--------|
| `config.py` | ✅ Done |
| `prompts.py` | ✅ Done (updatable) |
| `api_client.py` | ✅ Done |
| `main.py` / Overlay UI | ✅ Done (CustomTkinter) |

### Contributing & license

Issues and PRs are welcome—especially from Korean/Japanese-speaking players who can provide more accurate localization examples. Please comply with Blizzard's Terms of Service; do not use this project for cheating or automated gameplay.
---

## License

MIT（予定 / TBD — 正式许可文件添加前请以仓库内 LICENSE 为准）
