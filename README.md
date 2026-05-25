# OW-Light-Translator

> 轻量级 · 实时 · 反作弊友好 · 守望先锋屏幕翻译 Overlay

**语言 / Language / 言語 / 언어：**
[中文](#zh) · [English](#en) · [日本語](#ja) · [한국어](#ko)

---

<a id="zh"></a>

## 中文

### 项目简介

**OW-Light-Translator** 是一款面向《守望先锋》玩家的**外部屏幕翻译工具**。你在亚服排到的韩文、日文、英文混排聊天——`힐좀`、`C9`、`support diff`、`源氏1hp`——框选区域后一键识别并翻成**国服玩家习惯的中文术语**，显示在透明 Overlay 上，不打断操作。

适合：

- 在亚服打竞技、快速交流但读不懂韩/日/英混排的玩家
- 想学习「外部 Overlay + 异步 OCR/LLM」架构的 Python 开发者

### 反作弊与安全设计

本工具**不读取、不写入游戏内存**，**不注入 DLL**，**不模拟键鼠输入**。仅使用 Windows 标准桌面截图（`mss` / Desktop Duplication）在外部窗口显示翻译结果，与 OBS、Discord Overlay 同类思路。

> ⚠️ 任何第三方工具的使用风险需自行评估。本项目与 Blizzard Entertainment 无关，也不保证不被反作弊系统标记——请谨慎使用。

### 核心特性

| 特性 | 说明 |
|------|------|
| 双模式 UI | **编辑模式**：可拖拽、缩放选区；**锁定模式**：无边框、透明、鼠标穿透、置顶 |
| 零磁盘 I/O | 截图在内存中直接转 Base64，不写临时文件 |
| 异步流水线 | UI / 热键不阻塞；截图 → OCR → 翻译在后台 `asyncio`  worker 中完成 |
| 本地过滤 | 纯英文/数字/标点经 Regex 过滤，跳过 LLM 调用，省 Token |
| OW 俚语专家 | 内置 DeepSeek System Prompt，覆盖 C9、Diff、英雄缩写、韩日常用 callout |

### 技术栈

- **UI**：PyQt6
- **截图**：mss
- **网络**：httpx + asyncio
- **热键**：keyboard
- **OCR**：智谱 GLM-OCR (`glm-ocr`)
- **翻译**：DeepSeek Chat (`deepseek-chat`)


### 工作流程

```
┌─────────────┐    Base64     ┌──────────┐    原文     ┌────────────┐
│ mss 屏幕截图 │ ────────────► │ GLM-OCR  │ ──────────► │ Regex 过滤 │
└─────────────┘   (内存)      └──────────┘             └──────┬─────┘
                                                              │ 需翻译
                                                              ▼
┌─────────────┐   中文译文    ┌──────────────┐
│ PyQt6 Overlay│ ◄────────── │ DeepSeek LLM │
└─────────────┘               └──────────────┘
```

### 项目结构

```
overwatch_translatetool/
├── main.py           # PyQt6 主程序、热键、async 事件循环
├── api_client.py     # GLM-OCR / DeepSeek 异步 HTTP 客户端
├── config.py         # DTO 与环境变量
├── prompts.py        # OW 俚语翻译 System Prompt
├── requirements.txt
└── README.md
```

### 开发状态

| 模块 | 状态 |
|------|------|
| `config.py` | ✅ 已完成 |
| `prompts.py` | ✅ 已完成 （可更新）|
| `api_client.py` | 🚧 进行中 |
| `main.py` | 🚧 进行中 |

### 贡献与许可

欢迎 Issue / PR，特别是懂韩语日语的玩家欢迎提供更精准的本地化翻译案例，也可以直接提供pr。请遵守 Blizzard 用户协议，勿将本项目用于作弊或自动化操作。

**[↑ 返回顶部](#ow-light-translator)**

---

<a id="en"></a>

## English

### Introduction

**OW-Light-Translator** is an **external screen-translation tool** for *Overwatch* players. When Asian-server chat mixes Korean, Japanese, and English—`힐좀`, `C9`, `support diff`, `genji 1hp`—you select a region, trigger capture with one hotkey, and get **mainland-Chinese gamer terminology** on a transparent overlay without interrupting gameplay.

Built for:

- Competitive players on Asian servers who need fast comms translation
- Python developers learning **external overlay + async OCR/LLM** architecture

### Anti-cheat & safety

This tool performs **zero memory read/write**, **zero DLL injection**, and **zero simulated input**. It only uses standard Windows desktop capture (`mss` / Desktop Duplication) and renders results in an external window—similar in approach to OBS or Discord overlay.

> ⚠️ Use at your own risk. Not affiliated with Blizzard Entertainment. No guarantee regarding anti-cheat compatibility—please proceed with caution.

### Key features

| Feature | Description |
|---------|-------------|
| Dual UI modes | **Edit mode**: draggable, resizable capture region; **Locked mode**: frameless, transparent, click-through, always on top |
| Zero disk I/O | Screenshots converted to Base64 in memory—no temp files |
| Async pipeline | Non-blocking UI and hotkeys; capture → OCR → translate on background `asyncio` workers |
| Local filter | Pure English/digits/punctuation filtered via Regex; skips LLM calls to save tokens |
| OW slang expert | Built-in DeepSeek System Prompt covering C9, Diff, hero shorthand, and common KR/JP callouts |

### Tech stack

- **UI**: PyQt6
- **Capture**: mss
- **Network**: httpx + asyncio
- **Hotkeys**: keyboard
- **OCR**: Zhipu GLM-OCR (`glm-ocr`)
- **Translation**: DeepSeek Chat (`deepseek-chat`)

### Workflow

```
┌─────────────┐    Base64     ┌──────────┐   raw text   ┌────────────┐
│ mss capture │ ────────────► │ GLM-OCR  │ ───────────► │ Regex filt │
└─────────────┘   (in RAM)    └──────────┘              └──────┬─────┘
                                                               │ translate
                                                               ▼
┌─────────────┐  CN translation ┌──────────────┐
│ PyQt6 Overlay│ ◄──────────── │ DeepSeek LLM │
└─────────────┘                 └──────────────┘
```

### Project structure

```
overwatch_translatetool/
├── main.py           # PyQt6 app, hotkeys, async event loop
├── api_client.py     # Async HTTP client for GLM-OCR / DeepSeek
├── config.py         # DTOs and environment variables
├── prompts.py        # OW slang translation System Prompt
├── requirements.txt
└── README.md
```

### Development status

| Module | Status |
|--------|--------|
| `config.py` | ✅ Done |
| `prompts.py` | ✅ Done (updatable) |
| `api_client.py` | 🚧 In progress |
| `main.py` | 🚧 In progress |

### Contributing & license

Issues and PRs are welcome—especially from Korean/Japanese-speaking players who can provide more accurate localization examples (PRs directly appreciated). Please comply with Blizzard's Terms of Service; do not use this project for cheating or automated gameplay.

**[↑ Back to top](#ow-light-translator)**

---

<a id="ja"></a>

## 日本語

### プロジェクト概要

**OW-Light-Translator** は『オーバーウォッチ』プレイヤー向けの**外部スクリーン翻訳ツール**です。アジアサーバーでよく見る韓国語・日本語・英語混在チャット——`힐좀`、`C9`、`support diff`、`源氏1hp`——を範囲指定してワンキーで認識し、**中国本土のゲーマーが慣れ親しんだ中文ゲーム用語**に翻訳、透明オーバーレイに表示します。操作を中断しません。

対象ユーザー：

- アジアサーバーで競技プレイ中、韓/日/英混在のやり取りを素早く理解したいプレイヤー
- 「外部 Overlay + 非同期 OCR/LLM」アーキテクチャを学びたい Python 開発者

### アンチチート・安全設計

本ツールはゲームメモリの**読み書きなし**、**DLL インジェクションなし**、**キー・マウス入力のシミュレーションなし**。Windows 標準のデスクトップキャプチャ（`mss` / Desktop Duplication）のみ使用し、外部ウィンドウに翻訳結果を表示します（OBS や Discord オーバーレイと同系統）。

> ⚠️ サードパーティツールの利用リスクは自己判断で。Blizzard Entertainment とは無関係であり、アンチチートによる検出がないことも保証しません——ご利用は慎重に。

### 主な機能

| 機能 | 内容 |
|------|------|
| デュアル UI | **編集モード**：ドラッグ・リサイズ可能；**ロックモード**：枠なし・透明・クリック透過・最前面 |
| ディスク I/O ゼロ | スクリーンショットをメモリ上で Base64 化、一時ファイルなし |
| 非同期パイプライン | UI / ホットキーをブロックしない；キャプチャ → OCR → 翻訳を `asyncio` ワーカーで実行 |
| ローカルフィルタ | 純英数字・句読点は Regex で除外、LLM 呼び出しをスキップして Token 節約 |
| OW スラング対応 | DeepSeek System Prompt 内蔵。C9、Diff、ヒーロー略称、韓日コールアウトをカバー |

### 技術スタック

- **UI**：PyQt6
- **キャプチャ**：mss
- **ネットワーク**：httpx + asyncio
- **ホットキー**：keyboard
- **OCR**：智譜 GLM-OCR（`glm-ocr`）
- **翻訳**：DeepSeek Chat（`deepseek-chat`）

### 処理フロー

```
┌─────────────┐    Base64     ┌──────────┐    原文     ┌────────────┐
│ mss 画面取得 │ ────────────► │ GLM-OCR  │ ──────────► │ Regex フィルタ │
└─────────────┘   (メモリ)    └──────────┘             └──────┬─────┘
                                                              │ 要翻訳
                                                              ▼
┌─────────────┐   中文訳文    ┌──────────────┐
│ PyQt6 Overlay│ ◄────────── │ DeepSeek LLM │
└─────────────┘               └──────────────┘
```

### プロジェクト構成

```
overwatch_translatetool/
├── main.py           # PyQt6 メイン、ホットキー、async イベントループ
├── api_client.py     # GLM-OCR / DeepSeek 非同期 HTTP クライアント
├── config.py         # DTO と環境変数
├── prompts.py        # OW スラング翻訳 System Prompt
├── requirements.txt
└── README.md
```

### 開発状況

| モジュール | 状態 |
|-----------|------|
| `config.py` | ✅ 完了 |
| `prompts.py` | ✅ 完了（更新可） |
| `api_client.py` | 🚧 開発中 |
| `main.py` | 🚧 開発中 |

### 貢献・ライセンス

Issue / PR 歓迎。特に韓国語・日本語に堪能なプレイヤーから、より正確なローカライズ翻訳例の提供や PR をお待ちしています。Blizzard 利用規約を遵守し、チートや自動操作用途での使用は禁止してください。

**[↑ トップへ](#ow-light-translator)**

---

<a id="ko"></a>

## 한국어

### 프로젝트 소개

**OW-Light-Translator**는 《오버워치》 플레이어를 위한 **외부 화면 번역 도구**입니다. 아시아 서버에서 흔한 한·일·영 혼합 채팅——`힐좀`, `C9`, `support diff`, `源氏1hp`——을 영역 지정 후 단축키 한 번으로 인식하고, **중국 본토 게이머들이 익숙한 표준 중문 게임 용어**로 번역해 투명 Overlay에 표시합니다. 게임 조작을 방해하지 않습니다.

추천 대상:

- 아시아 서버 경쟁전에서 빠른 소통 번역이 필요하지만 한/일/영 혼합 채팅을 읽기 어려운 플레이어
- 「외부 Overlay + 비동기 OCR/LLM」아키텍처를 배우고 싶은 Python 개발자

### 안티치트·보안 설계

본 도구는 게임 메모리 **읽기/쓰기 없음**, **DLL 인젝션 없음**, **키·마우스 입력 시뮬레이션 없음**. Windows 표준 데스크톱 캡처(`mss` / Desktop Duplication)만 사용하며, 외부 창에 번역 결과를 표시합니다(OBS·Discord Overlay와 유사한 방식).

> ⚠️ 서드파티 도구 사용 위험은 본인이 판단해야 합니다. Blizzard Entertainment와 무관하며, 안티치트 시스템에 의해 표시되지 않는다고 보장하지 않습니다——신중히 사용하세요.

### 핵심 기능

| 기능 | 설명 |
|------|------|
| 듀얼 UI | **편집 모드**: 드래그·리사이즈 가능；**잠금 모드**: 테두리 없음·투명·클릭 통과·항상 위 |
| 디스크 I/O 제로 | 스크린샷을 메모리에서 Base64로 변환, 임시 파일 없음 |
| 비동기 파이프라인 | UI / 핫키 논블로킹；캡처 → OCR → 번역을 백그라운드 `asyncio` worker에서 처리 |
| 로컬 필터 | 순수 영문·숫자·구두점은 Regex로 필터링, LLM 호출 스킵으로 Token 절약 |
| OW 슬랭 전문 | DeepSeek System Prompt 내장. C9, Diff, 영웅 약어, 한·일 콜아웃 커버 |

### 기술 스택

- **UI**: PyQt6
- **캡처**: mss
- **네트워크**: httpx + asyncio
- **핫키**: keyboard
- **OCR**: 智谱 GLM-OCR (`glm-ocr`)
- **번역**: DeepSeek Chat (`deepseek-chat`)

### 처리 흐름

```
┌─────────────┐    Base64     ┌──────────┐    원문     ┌────────────┐
│ mss 화면캡처 │ ────────────► │ GLM-OCR  │ ──────────► │ Regex 필터 │
└─────────────┘   (메모리)    └──────────┘             └──────┬─────┘
                                                              │ 번역 필요
                                                              ▼
┌─────────────┐   중문 번역     ┌──────────────┐
│ PyQt6 Overlay│ ◄────────── │ DeepSeek LLM │
└─────────────┘               └──────────────┘
```

### 프로젝트 구조

```
overwatch_translatetool/
├── main.py           # PyQt6 메인, 핫키, async 이벤트 루프
├── api_client.py     # GLM-OCR / DeepSeek 비동기 HTTP 클라이언트
├── config.py         # DTO 및 환경 변수
├── prompts.py        # OW 슬랭 번역 System Prompt
├── requirements.txt
└── README.md
```

### 개발 현황

| 모듈 | 상태 |
|------|------|
| `config.py` | ✅ 완료 |
| `prompts.py` | ✅ 완료 (업데이트 가능) |
| `api_client.py` | 🚧 진행 중 |
| `main.py` | 🚧 진행 중 |

### 기여·라이선스

Issue / PR 환영합니다. 특히 한국어·일본어에 능숙한 플레이어의 더 정확한 현지화 번역 사례 제공 및 PR을 기대합니다. Blizzard 이용약관을 준수하고, 치트·자동 조작 용도로 사용하지 마세요.

**[↑ 맨 위로](#ow-light-translator)**

---

## License

MIT（予定 / TBD — 正式许可文件添加前请以仓库内 LICENSE 为准）
