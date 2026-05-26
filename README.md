# OW-Light-Translator

> 轻量级 · 实时 · 反作弊友好 · 守望先锋屏幕翻译 Overlay

<p align="center">
  <strong>Language / 语言 / 言語 / 언어</strong><br/>
  点击标签切换页面，无需滚动 · Click a tab to switch — no scrolling
</p>

<!-- markdownlint-disable MD033 -->

<input type="radio" name="lang" id="lang-zh" checked="checked" hidden="hidden">
<input type="radio" name="lang" id="lang-en" hidden="hidden">
<input type="radio" name="lang" id="lang-ja" hidden="hidden">
<input type="radio" name="lang" id="lang-ko" hidden="hidden">

<div align="center" class="lang-tabs">
  <label for="lang-zh"><img alt="中文" src="https://img.shields.io/badge/中文-ZH-red?style=for-the-badge"></label>
  <label for="lang-en"><img alt="English" src="https://img.shields.io/badge/English-EN-blue?style=for-the-badge"></label>
  <label for="lang-ja"><img alt="日本語" src="https://img.shields.io/badge/日本語-JA-green?style=for-the-badge"></label>
  <label for="lang-ko"><img alt="한국어" src="https://img.shields.io/badge/한국어-KO-orange?style=for-the-badge"></label>
</div>

<div class="lang-panel lang-zh">

## 中文

### 项目简介

**OW-Light-Translator** 是一款面向《守望先锋》玩家的**外部屏幕翻译工具**。你在亚服排到的韩文、日文、英文混排聊天——`힐좀`、`C9`、`support diff`、`源氏1hp`——框选区域后一键识别并翻成**国服玩家习惯的中文术语**，显示在透明 Overlay 上，不打断操作。

适合：

- 在亚服打竞技、快速交流但读不懂韩/日/英混排的玩家
- 想学习「外部 Overlay + 异步 OCR/LLM」架构的 Python 开发者

### 反作弊与安全设计

本工具**不读取、不写入游戏内存**，**不注入 DLL**，**不模拟键鼠输入**。仅使用 Windows 标准桌面截图（`mss` / Desktop Duplication）在外部窗口显示翻译结果，与 OBS、Discord Overlay 同类思路。

> ⚠️ 任何第三方工具的使用风险需自行评估。本项目与 Blizzard Entertainment 无关，也不保证不被反作弊系统标记——请谨慎使用。

### OCR 识别说明

目前 OCR 的识别以**默认设置**为主：按《守望先锋》聊天框四类语义颜色（敌方 / 友方 / 队伍 / 系统提示）进行多通道掩码识别，颜色范围见 `config.py` 中的 `COLOR_PALETTE`。

<p align="center">
  <img src="img/font_color.png" alt="OW 聊天字体颜色语义对照" width="720">
</p>

> 上图：游戏内聊天文字颜色与语义标签对应关系。Enemy（红）、Friendly（蓝）、Group（绿）、Alert（橙）。

### 核心特性

| 特性 | 说明 |
|------|------|
| 双模式 UI | **编辑模式**：可拖拽、缩放选区；**锁定模式**：无边框、透明、鼠标穿透、置顶 |
| 零磁盘 I/O | 截图在内存中直接转 Base64，不写临时文件 |
| 多通道 OCR | 按颜色掩码分通道识别，降低复杂背景干扰 |
| 异步流水线 | UI / 热键不阻塞；截图 → OCR → 翻译在后台 `asyncio` worker 中完成 |
| OW 俚语专家 | 内置 DeepSeek System Prompt，覆盖 C9、Diff、英雄缩写、韩日常用 callout |

### 工作流程

```
┌─────────────┐   颜色掩码    ┌──────────┐    原文     ┌──────────────┐
│ mss 屏幕截图 │ ────────────► │ GLM-OCR  │ ──────────► │ DeepSeek 翻译 │
└─────────────┘   (内存)      └──────────┘             └──────┬───────┘
                                                              │
                                                              ▼
                                                     ┌─────────────┐
                                                     │ PyQt6 Overlay│
                                                     └─────────────┘
```

### 项目结构

```
overwatch_translate_tool/
├── main.py            # PyQt6 主程序、热键、async 事件循环
├── api_client.py      # GLM-OCR / DeepSeek 异步 HTTP 客户端
├── config.py          # DTO 与环境变量
├── prompts.py         # OW 俚语翻译 System Prompt
├── local_api_keys.py  # 本地 API Key（已 gitignore）
├── img/
│   └── font_color.png # 聊天颜色语义参考图
├── requirements.txt
└── README.md
```

### 开发者指南

面向希望参与本项目的开发者，本节汇总环境、技术栈与协作流程。

#### 环境要求

| 类别 | 要求 | 说明 |
|------|------|------|
| 操作系统 | **Windows 10/11** | 主运行环境；`mss` 桌面截图、`keyboard` 全局热键在 Windows 上最稳定 |
| Python | **3.10+**（推荐 3.11 / 3.12） | 项目使用 `dataclass(slots=True)` 等现代语法 |
| 包管理 | `pip` + `venv` | 建议使用虚拟环境隔离依赖 |
| 版本控制 | **Git** | Fork → 分支 → PR 协作 |
| IDE | **VS Code / Cursor** | 推荐安装 Python、Pylance；调试 Overlay 时建议双屏 |
| 可选 | 《守望先锋》客户端 | 联调截图/OCR 时需要；纯 API 层开发可不启动游戏 |

#### 技术栈

| 层级 | 库 / 服务 | 版本约束 | 在本项目中的作用 |
|------|-----------|----------|------------------|
| UI | [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) | `>=6.6.0` | 无边框悬浮窗、拖拽缩放、锁定穿透、按颜色渲染译文 |
| 截图 | [mss](https://python-mss.readthedocs.io/) | `>=9.0.1` | 区域桌面截图，内存直出，不写临时文件 |
| 图像处理 | [OpenCV](https://opencv.org/) | `>=4.10` | `inRange` 颜色掩码、形态学降噪、PNG 内存编码 |
| 数值计算 | [NumPy](https://numpy.org/) | `>=1.26` | 截图帧与掩码数组运算 |
| 图像辅助 | [Pillow](https://python-pillow.org/) | `>=10.3` | 图像格式互转（预留/辅助） |
| 网络 | [httpx](https://www.python-httpx.org/) | `>=0.27` | GLM-OCR、DeepSeek 异步 HTTP 请求 |
| 并发 | `asyncio`（标准库） | — | UI 主线程与 OCR/翻译 worker 解耦 |
| 热键 | [keyboard](https://github.com/boppreh/keyboard) | `>=0.13.5` | 全局快捷键（截图、锁定切换等） |
| 配置 | [python-dotenv](https://github.com/theskumar/python-dotenv) | `>=1.0` | 读取 `.env` 中的 URL、超时等可选配置 |
| OCR API | 智谱 **GLM-OCR** (`glm-ocr`) | — | 多通道掩码图文字识别 |
| 翻译 API | **DeepSeek Chat** (`deepseek-chat`) | — | OW 亚服俚语 → 中文竞技术语 |

#### 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/<your-org>/overwatch_translate_tool.git
cd overwatch_translate_tool

# 2. 创建并激活虚拟环境（Windows PowerShell 示例）
python -m venv .venv
.venv\Scripts\Activate.ps1

# 3. 安装依赖
pip install -U pip
pip install -r requirements.txt

# 4. 配置 API Key（见下方「密钥配置」）
# 5. 启动主程序（main.py 完成后）
python main.py
```

#### 密钥配置

在项目根目录编辑 `local_api_keys.py`（已加入 `.gitignore`，不会提交到 Git）：

```python
GLM_API_KEY = "你的智谱 GLM Key"
DEEPSEEK_API_KEY = "你的 DeepSeek Key"
```

也可选用 `.env` 作为备选（优先级：`local_api_keys.py` > 环境变量）：

```env
GLM_API_KEY=...
DEEPSEEK_API_KEY=...
GLM_OCR_URL=https://open.bigmodel.cn/api/paas/v4/chat/completions
DEEPSEEK_URL=https://api.deepseek.com/chat/completions
HTTP_TIMEOUT_SEC=30
```

#### 模块职责（改哪里）

| 文件 | 职责 | 典型改动 |
|------|------|----------|
| `config.py` | DTO、`COLOR_PALETTE`、API 端点 | 调整聊天颜色掩码范围、超时时间 |
| `prompts.py` | OCR/翻译 Prompt、消息体构造 | 补充 OW 俚语、优化翻译风格 |
| `api_client.py` | 截图、颜色掩码、OCR/翻译 HTTP | 并发策略、错误重试、响应解析 |
| `main.py` | PyQt6 UI、热键、async 事件循环 | Overlay 交互、渲染逻辑 |
| `local_api_keys.py` | 本地密钥 | 仅本机填写，勿提交 |
| `img/font_color.png` | 颜色语义参考图 | 更新 OW 聊天配色对照 |

#### 参与开发流程

```
Fork 仓库
   │
   ▼
git checkout -b feat/your-feature    ← 从 main 拉功能分支
   │
   ▼
修改代码 + 本地验证                  ← 见下方「本地调试建议」
   │
   ▼
git commit / git push
   │
   ▼
发起 Pull Request                    ← 说明改动模块与测试方式
```

**PR 建议包含：**

- 改动动机（Bug / 功能 / Prompt 优化）
- 影响模块（如 `api_client.py`、`prompts.py`）
- 本地验证步骤（是否需游戏窗口、是否仅测 API）

#### 本地调试建议

**不启动游戏（API 层）：** 可在 Python REPL 或临时脚本中调用 `api_client`：

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

**联调 Overlay（需 Windows + 游戏）：** 运行 `python main.py`，框选聊天区域，用热键触发截图 → OCR → 翻译链路。

**常见排查：**

| 现象 | 检查项 |
|------|--------|
| OCR 无输出 | `GLM_API_KEY`、掩码颜色范围（`COLOR_PALETTE`）、截图区域是否覆盖聊天框 |
| 翻译为空 | `DEEPSEEK_API_KEY`、网络代理、`prompts.py` 输出格式 |
| 热键无效 | Windows 是否以管理员运行（`keyboard` 偶需）、快捷键冲突 |
| 依赖导入失败 | 虚拟环境是否激活、`pip install -r requirements.txt` 是否成功 |

### 开发状态

| 模块 | 状态 |
|------|------|
| `config.py` | ✅ 已完成 |
| `prompts.py` | ✅ 已完成（可更新） |
| `api_client.py` | ✅ 已完成 |
| `main.py` | 🚧 进行中 |

### 贡献与许可

欢迎 Issue / PR，特别是懂韩语日语的玩家欢迎提供更精准的本地化翻译案例。请遵守 Blizzard 用户协议，勿将本项目用于作弊或自动化操作。

</div>

<div class="lang-panel lang-en">

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

```
┌─────────────┐  color mask   ┌──────────┐   raw text   ┌──────────────┐
│ mss capture │ ────────────► │ GLM-OCR  │ ───────────► │ DeepSeek LLM │
└─────────────┘   (in RAM)    └──────────┘              └──────┬───────┘
                                                               │
                                                               ▼
                                                      ┌─────────────┐
                                                      │ PyQt6 Overlay│
                                                      └─────────────┘
```

### Project structure

```
overwatch_translate_tool/
├── main.py            # PyQt6 app, hotkeys, async event loop
├── api_client.py      # Async HTTP client for GLM-OCR / DeepSeek
├── config.py          # DTOs and environment variables
├── prompts.py         # OW slang translation System Prompt
├── local_api_keys.py  # Local API keys (gitignored)
├── img/
│   └── font_color.png # Chat color semantics reference
├── requirements.txt
└── README.md
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
| UI | [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) | `>=6.6.0` | Frameless overlay, drag/resize, click-through lock mode, color-coded rendering |
| Capture | [mss](https://python-mss.readthedocs.io/) | `>=9.0.1` | Region desktop capture, in-memory only |
| Image | [OpenCV](https://opencv.org/) | `>=4.10` | Color masking (`inRange`), morphology, in-memory PNG encode |
| Numeric | [NumPy](https://numpy.org/) | `>=1.26` | Frame and mask array operations |
| Image | [Pillow](https://python-pillow.org/) | `>=10.3` | Image format helpers |
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

python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows PowerShell

pip install -U pip
pip install -r requirements.txt

# Configure API keys (see below), then:
python main.py                      # once main.py is ready
```

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
| `main.py` | PyQt6 UI, hotkeys, async loop | Overlay UX, rendering |
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
| `main.py` | 🚧 In progress |

### Contributing & license

Issues and PRs are welcome—especially from Korean/Japanese-speaking players who can provide more accurate localization examples. Please comply with Blizzard's Terms of Service; do not use this project for cheating or automated gameplay.

</div>

<div class="lang-panel lang-ja">

## 日本語

### プロジェクト概要

**OW-Light-Translator** は『オーバーウォッチ』プレイヤー向けの**外部スクリーン翻訳ツール**です。アジアサーバーでよく見る韓国語・日本語・英語混在チャット——`힐좀`、`C9`、`support diff`、`源氏1hp`——を範囲指定してワンキーで認識し、**中国本土のゲーマーが慣れ親しんだ中文ゲーム用語**に翻訳、透明オーバーレイに表示します。操作を中断しません。

対象ユーザー：

- アジアサーバーで競技プレイ中、韓/日/英混在のやり取りを素早く理解したいプレイヤー
- 「外部 Overlay + 非同期 OCR/LLM」アーキテクチャを学びたい Python 開発者

### アンチチート・安全設計

本ツールはゲームメモリの**読み書きなし**、**DLL インジェクションなし**、**キー・マウス入力のシミュレーションなし**。Windows 標準のデスクトップキャプチャ（`mss` / Desktop Duplication）のみ使用し、外部ウィンドウに翻訳結果を表示します（OBS や Discord オーバーレイと同系統）。

> ⚠️ サードパーティツールの利用リスクは自己判断で。Blizzard Entertainment とは無関係であり、アンチチートによる検出がないことも保証しません——ご利用は慎重に。

### OCR 認識について

現在の OCR は**デフォルト設定**を前提としています。『オーバーウォッチ』チャットの 4 種類の意味色（敵 / 味方 / パーティ / システム）ごとにマスクを分けて認識します。色範囲は `config.py` の `COLOR_PALETTE` を参照してください。

<p align="center">
  <img src="img/font_color.png" alt="OW チャット文字色の意味対応" width="720">
</p>

> 上図：ゲーム内チャット文字色と意味タグの対応。Enemy（赤）、Friendly（青）、Group（緑）、Alert（橙）。

### 主な機能

| 機能 | 内容 |
|------|------|
| デュアル UI | **編集モード**：ドラッグ・リサイズ可能；**ロックモード**：枠なし・透明・クリック透過・最前面 |
| ディスク I/O ゼロ | スクリーンショットをメモリ上で Base64 化、一時ファイルなし |
| マルチチャネル OCR | 色マスクでチャネル分離し、背景ノイズを低減 |
| 非同期パイプライン | UI / ホットキーをブロックしない；キャプチャ → OCR → 翻訳を `asyncio` ワーカーで実行 |
| OW スラング対応 | DeepSeek System Prompt 内蔵。C9、Diff、ヒーロー略称、韓日コールアウトをカバー |

### 処理フロー

```
┌─────────────┐   色マスク    ┌──────────┐    原文     ┌──────────────┐
│ mss 画面取得 │ ────────────► │ GLM-OCR  │ ──────────► │ DeepSeek 翻訳 │
└─────────────┘   (メモリ)    └──────────┘             └──────┬───────┘
                                                              │
                                                              ▼
                                                     ┌─────────────┐
                                                     │ PyQt6 Overlay│
                                                     └─────────────┘
```

### プロジェクト構成

```
overwatch_translate_tool/
├── main.py            # PyQt6 メイン、ホットキー、async イベントループ
├── api_client.py      # GLM-OCR / DeepSeek 非同期 HTTP クライアント
├── config.py          # DTO と環境変数
├── prompts.py         # OW スラング翻訳 System Prompt
├── local_api_keys.py  # ローカル API Key（gitignore 対象）
├── img/
│   └── font_color.png # チャット色意味の参考図
├── requirements.txt
└── README.md
```

### 開発者ガイド

本プロジェクトに参加する開発者向け：環境・技術スタック・協業フローをまとめています。

#### 環境要件

| 項目 | 要件 | 補足 |
|------|------|------|
| OS | **Windows 10/11** | 主ターゲット；`mss` キャプチャと `keyboard` ホットキーは Windows が最安定 |
| Python | **3.10+**（3.11 / 3.12 推奨） | `dataclass(slots=True)` 等のモダン構文を使用 |
| パッケージ | `pip` + `venv` | 仮想環境の利用を推奨 |
| VCS | **Git** | Fork → ブランチ → PR |
| IDE | **VS Code / Cursor** | Python + Pylance；Overlay デバッグはデュアルモニター推奨 |
| 任意 | 『OW』クライアント | 実画面 OCR 調整時のみ必要；API 層のみなら不要 |

#### 技術スタック

| レイヤ | ライブラリ / サービス | バージョン | 役割 |
|--------|----------------------|------------|------|
| UI | [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) | `>=6.6.0` | フレームレス Overlay、ドラッグ、クリック透過、色付き描画 |
| キャプチャ | [mss](https://python-mss.readthedocs.io/) | `>=9.0.1` | 領域スクリーンショット（メモリのみ） |
| 画像 | [OpenCV](https://opencv.org/) | `>=4.10` | 色マスク、モルフォロジー、PNG メモリエンコード |
| 数値 | [NumPy](https://numpy.org/) | `>=1.26` | フレーム・マスク配列演算 |
| 画像 | [Pillow](https://python-pillow.org/) | `>=10.3` | 画像フォーマット補助 |
| ネットワーク | [httpx](https://www.python-httpx.org/) | `>=0.27` | GLM-OCR / DeepSeek 非同期 HTTP |
| 並行 | `asyncio`（標準） | — | UI と OCR/翻訳 worker の分離 |
| ホットキー | [keyboard](https://github.com/boppreh/keyboard) | `>=0.13.5` | グローバルショートカット |
| 設定 | [python-dotenv](https://github.com/theskumar/python-dotenv) | `>=1.0` | `.env` による URL・タイムアウト等 |
| OCR API | 智譜 **GLM-OCR** | — | マルチチャネル OCR |
| 翻訳 API | **DeepSeek Chat** | — | OW スラング → 中文 |

#### クイックスタート

```bash
git clone https://github.com/<your-org>/overwatch_translate_tool.git
cd overwatch_translate_tool

python -m venv .venv
.venv\Scripts\Activate.ps1

pip install -U pip
pip install -r requirements.txt

python main.py    # main.py 完成後
```

#### API Key 設定

ルートの `local_api_keys.py` を編集（gitignore 済み）：

```python
GLM_API_KEY = "智譜 GLM の Key"
DEEPSEEK_API_KEY = "DeepSeek の Key"
```

`.env` も利用可（優先：`local_api_keys.py` > 環境変数）。

#### モジュール分担

| ファイル | 責務 | 典型的な変更 |
|----------|------|--------------|
| `config.py` | DTO、`COLOR_PALETTE` | 色マスク範囲、タイムアウト |
| `prompts.py` | Prompt 構築 | スラング辞書、翻訳トーン |
| `api_client.py` | キャプチャ・OCR・翻訳 | 並行数、リトライ、パース |
| `main.py` | PyQt6 UI | Overlay 操作、描画 |
| `local_api_keys.py` | ローカル秘密情報 | コミット禁止 |

#### 開発フロー

Fork → `git checkout -b feat/xxx` → 実装・検証 → commit/push → Pull Request

**PR に含めること：** 変更理由、影響モジュール、テスト方法（API のみ / ゲーム連携）。

#### ローカルデバッグ

```python
import asyncio
from api_client import capture_region_to_base64, process_multi_channel_ocr, translate_ocr_results

async def smoke_test():
    capture = capture_region_to_base64({"left": 0, "top": 0, "width": 800, "height": 400})
    ocr = await process_multi_channel_ocr(capture)
    print(await translate_ocr_results(ocr))

asyncio.run(smoke_test())
```

| 症状 | 確認項目 |
|------|----------|
| OCR 空 | `GLM_API_KEY`、`COLOR_PALETTE`、キャプチャ範囲 |
| 翻訳空 | `DEEPSEEK_API_KEY`、ネットワーク、`prompts.py` |
| ホットキー無効 | 管理者実行、ショートカット競合 |
| import 失敗 | venv 有効化、`pip install -r requirements.txt` |

### 開発状況

| モジュール | 状態 |
|-----------|------|
| `config.py` | ✅ 完了 |
| `prompts.py` | ✅ 完了（更新可） |
| `api_client.py` | ✅ 完了 |
| `main.py` | 🚧 開発中 |

### 貢献・ライセンス

Issue / PR 歓迎。特に韓国語・日本語に堪能なプレイヤーから、より正確なローカライズ翻訳例の提供や PR をお待ちしています。Blizzard 利用規約を遵守し、チートや自動操作用途での使用は禁止してください。

</div>

<div class="lang-panel lang-ko">

## 한국어

### 프로젝트 소개

**OW-Light-Translator**는 《오버워치》 플레이어를 위한 **외부 화면 번역 도구**입니다. 아시아 서버에서 흔한 한·일·영 혼합 채팅——`힐좀`, `C9`, `support diff`, `源氏1hp`——을 영역 지정 후 단축키 한 번으로 인식하고, **중국 본토 게이머들이 익숙한 표준 중문 게임 용어**로 번역해 투명 Overlay에 표시합니다. 게임 조작을 방해하지 않습니다.

추천 대상:

- 아시아 서버 경쟁전에서 빠른 소통 번역이 필요하지만 한/일/영 혼합 채팅을 읽기 어려운 플레이어
- 「외부 Overlay + 비동기 OCR/LLM」아키텍처를 배우고 싶은 Python 개발자

### 안티치트·보안 설계

본 도구는 게임 메모리 **읽기/쓰기 없음**, **DLL 인젝션 없음**, **키·마우스 입력 시뮬레이션 없음**. Windows 표준 데스크톱 캡처(`mss` / Desktop Duplication)만 사용하며, 외부 창에 번역 결과를 표시합니다(OBS·Discord Overlay와 유사한 방식).

> ⚠️ 서드파티 도구 사용 위험은 본인이 판단해야 합니다. Blizzard Entertainment와 무관하며, 안티치트 시스템에 의해 표시되지 않는다고 보장하지 않습니다——신중히 사용하세요.

### OCR 인식 안내

현재 OCR은 **기본 설정**을 기준으로 동작합니다. 《오버워치》 채팅의 4가지 의미 색상(적 / 아군 / 파티 / 시스템)별로 마스크 채널을 나눠 인식하며, 색상 범위는 `config.py`의 `COLOR_PALETTE`에 정의되어 있습니다.

<p align="center">
  <img src="img/font_color.png" alt="OW 채팅 글자색 의미 대응" width="720">
</p>

> 위 그림: 게임 내 채팅 글자색과 의미 태그 대응. Enemy(빨강), Friendly(파랑), Group(초록), Alert(주황).

### 핵심 기능

| 기능 | 설명 |
|------|------|
| 듀얼 UI | **편집 모드**: 드래그·리사이즈 가능；**잠금 모드**: 테두리 없음·투명·클릭 통과·항상 위 |
| 디스크 I/O 제로 | 스크린샷을 메모리에서 Base64로 변환, 임시 파일 없음 |
| 멀티 채널 OCR | 색상 마스크로 채널 분리, 배경 노이즈 감소 |
| 비동기 파이프라인 | UI / 핫키 논블로킹；캡처 → OCR → 번역을 백그라운드 `asyncio` worker에서 처리 |
| OW 슬랭 전문 | DeepSeek System Prompt 내장. C9, Diff, 영웅 약어, 한·일 콜아웃 커버 |

### 처리 흐름

```
┌─────────────┐   색상 마스크  ┌──────────┐    원문     ┌──────────────┐
│ mss 화면캡처 │ ────────────► │ GLM-OCR  │ ──────────► │ DeepSeek 번역 │
└─────────────┘   (메모리)    └──────────┘             └──────┬───────┘
                                                              │
                                                              ▼
                                                     ┌─────────────┐
                                                     │ PyQt6 Overlay│
                                                     └─────────────┘
```

### 프로젝트 구조

```
overwatch_translate_tool/
├── main.py            # PyQt6 메인, 핫키, async 이벤트 루프
├── api_client.py      # GLM-OCR / DeepSeek 비동기 HTTP 클라이언트
├── config.py          # DTO 및 환경 변수
├── prompts.py         # OW 슬랭 번역 System Prompt
├── local_api_keys.py  # 로컬 API Key (gitignore)
├── img/
│   └── font_color.png # 채팅 색상 의미 참고 이미지
├── requirements.txt
└── README.md
```

### 개발자 가이드

기여 개발자를 위한 환경·기술 스택·협업 절차 안내입니다.

#### 환경 요구사항

| 항목 | 요구 | 비고 |
|------|------|------|
| OS | **Windows 10/11** | 주 타깃；`mss` 캡처·`keyboard` 단축키는 Windows에서 가장 안정적 |
| Python | **3.10+** (3.11 / 3.12 권장) | `dataclass(slots=True)` 등 최신 문법 사용 |
| 패키지 | `pip` + `venv` | 가상환경 사용 권장 |
| VCS | **Git** | Fork → 브랜치 → PR |
| IDE | **VS Code / Cursor** | Python + Pylance；Overlay 디버깅 시 듀얼 모니터 권장 |
| 선택 | 《오버워치》 클라이언트 | 실제 화면 OCR 튜닝 시 필요；API만 작업 시 불필요 |

#### 기술 스택

| 계층 | 라이브러리 / 서비스 | 버전 | 역할 |
|------|---------------------|------|------|
| UI | [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) | `>=6.6.0` | 프레임리스 Overlay, 드래그, 클릭 통과, 색상 렌더링 |
| 캡처 | [mss](https://python-mss.readthedocs.io/) | `>=9.0.1` | 영역 스크린샷 (메모리 전용) |
| 이미지 | [OpenCV](https://opencv.org/) | `>=4.10` | 색상 마스크, 모폴로지, PNG 메모리 인코딩 |
| 수치 | [NumPy](https://numpy.org/) | `>=1.26` | 프레임·마스크 배열 연산 |
| 이미지 | [Pillow](https://python-pillow.org/) | `>=10.3` | 이미지 포맷 보조 |
| 네트워크 | [httpx](https://www.python-httpx.org/) | `>=0.27` | GLM-OCR / DeepSeek 비동기 HTTP |
| 동시성 | `asyncio` (표준) | — | UI와 OCR/번역 worker 분리 |
| 핫키 | [keyboard](https://github.com/boppreh/keyboard) | `>=0.13.5` | 전역 단축키 |
| 설정 | [python-dotenv](https://github.com/theskumar/python-dotenv) | `>=1.0` | `.env` URL·타임아웃 |
| OCR API | 智谱 **GLM-OCR** | — | 멀티 채널 OCR |
| 번역 API | **DeepSeek Chat** | — | OW 슬랭 → 중문 |

#### 빠른 시작

```bash
git clone https://github.com/<your-org>/overwatch_translate_tool.git
cd overwatch_translate_tool

python -m venv .venv
.venv\Scripts\Activate.ps1

pip install -U pip
pip install -r requirements.txt

python main.py    # main.py 완료 후
```

#### API Key 설정

루트 `local_api_keys.py` 편집 (gitignore):

```python
GLM_API_KEY = "智谱 GLM Key"
DEEPSEEK_API_KEY = "DeepSeek Key"
```

`.env` 대체 가능 (우선순위: `local_api_keys.py` > 환경 변수).

#### 모듈 역할

| 파일 | 책임 | 일반적인 변경 |
|------|------|---------------|
| `config.py` | DTO, `COLOR_PALETTE` | 색상 마스크, 타임아웃 |
| `prompts.py` | Prompt | 슬랭, 번역 톤 |
| `api_client.py` | 캡처·OCR·번역 | 동시성, 재시도, 파싱 |
| `main.py` | PyQt6 UI | Overlay UX |
| `local_api_keys.py` | 로컬 키 | 커밋 금지 |

#### 기여 절차

Fork → `git checkout -b feat/xxx` → 구현·검증 → commit/push → Pull Request

**PR 포함 사항:** 변경 이유, 영향 모듈, 테스트 방법 (API만 / 게임 연동).

#### 로컬 디버깅

```python
import asyncio
from api_client import capture_region_to_base64, process_multi_channel_ocr, translate_ocr_results

async def smoke_test():
    capture = capture_region_to_base64({"left": 0, "top": 0, "width": 800, "height": 400})
    ocr = await process_multi_channel_ocr(capture)
    print(await translate_ocr_results(ocr))

asyncio.run(smoke_test())
```

| 증상 | 확인 |
|------|------|
| OCR 비어 있음 | `GLM_API_KEY`, `COLOR_PALETTE`, 캡처 영역 |
| 번역 비어 있음 | `DEEPSEEK_API_KEY`, 네트워크, `prompts.py` |
| 핫키 무반응 | 관리자 실행, 단축키 충돌 |
| import 오류 | venv 활성화, `pip install -r requirements.txt` |

### 개발 현황

| 모듈 | 상태 |
|------|------|
| `config.py` | ✅ 완료 |
| `prompts.py` | ✅ 완료 (업데이트 가능) |
| `api_client.py` | ✅ 완료 |
| `main.py` | 🚧 진행 중 |

### 기여·라이선스

Issue / PR 환영합니다. 특히 한국어·일본어에 능숙한 플레이어의 더 정확한 현지화 번역 사례 제공 및 PR을 기대합니다. Blizzard 이용약관을 준수하고, 치트·자동 조작 용도로 사용하지 마세요.

</div>

<style>
  .lang-tabs {
    margin: 12px 0 20px;
    user-select: none;
  }

  .lang-tabs label {
    cursor: pointer;
    margin: 0 6px;
    opacity: 0.72;
  }

  .lang-panel {
    display: none;
    border-top: 1px solid #30363d;
    padding-top: 24px;
  }

  #lang-zh:checked ~ .lang-zh,
  #lang-en:checked ~ .lang-en,
  #lang-ja:checked ~ .lang-ja,
  #lang-ko:checked ~ .lang-ko {
    display: block;
  }

  #lang-zh:checked ~ .lang-tabs label[for="lang-zh"],
  #lang-en:checked ~ .lang-tabs label[for="lang-en"],
  #lang-ja:checked ~ .lang-tabs label[for="lang-ja"],
  #lang-ko:checked ~ .lang-tabs label[for="lang-ko"] {
    opacity: 1;
  }
</style>

<!-- markdownlint-enable MD033 -->

---

## License

MIT（予定 / TBD — 正式许可文件添加前请以仓库内 LICENSE 为准）
