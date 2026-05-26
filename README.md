# OW-Light-Translator

> 轻量级 · 实时 · 反作弊友好 · 守望先锋屏幕翻译 Overlay

**Language / 语言 / 言語 / 언어：** **中文** | [English](README.en.md) | [日本語](README.ja.md) | [한국어](README.ko.md)

---

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

<p align="center">
  <img src="img/image.png" alt="OW-Light-Translator 详细系统流程图" width="900">
</p>

> 上图：完整数据流——`mss` 区域截图（内存 Base64）→ 按 `COLOR_PALETTE` 多通道颜色掩码 → 智谱 GLM-OCR 识别 → DeepSeek 本地化翻译 → PyQt6 Overlay 按语义颜色渲染译文。

### 项目结构

```
overwatch_translate_tool/
├── main.py            # PyQt6 主程序、热键、async 事件循环
├── api_client.py      # GLM-OCR / DeepSeek 异步 HTTP 客户端
├── config.py          # DTO 与环境变量
├── prompts.py         # OW 俚语翻译 System Prompt
├── local_api_keys.py  # 本地 API Key（已 gitignore）
├── img/
│   ├── image.png      # 详细系统流程图
│   └── font_color.png # 聊天颜色语义参考图
├── requirements.txt
├── README.md
├── README.en.md
├── README.ja.md
└── README.ko.md
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
---

## License

MIT（予定 / TBD — 正式许可文件添加前请以仓库内 LICENSE 为准）
