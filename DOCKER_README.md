# Docker 开发环境使用指南

> **说明**：本项目 Overlay GUI 基于 **CustomTkinter + Windows API**（`pywin32`、全局热键、鼠标穿透），**必须在 Windows 宿主机**运行 `python main.py`。Docker 环境仅用于 **API 层开发联调**，无法显示悬浮窗或截取宿主机游戏画面。

---

## 虚拟环境（venv）

本项目使用标准库 `venv`，虚拟环境目录名为 **`venv/`**（已在 `.gitignore`，不会上传）。

### Windows（推荐）

```powershell
# 克隆后，在项目根目录执行其一：

# 双击
scripts\setup_venv.bat

# 或 PowerShell
.\scripts\setup_venv.ps1

# 激活
.\venv\Scripts\Activate.ps1

# 启动
python main.py
```

### Linux / macOS

```bash
chmod +x scripts/setup_venv.sh
./scripts/setup_venv.sh
source venv/bin/activate
```

> Overlay GUI 完整功能仅 Windows 可用；Linux/macOS 脚本主要用于安装 API 依赖。

---

## 快速开始

### Windows 用户

双击运行 `start_dev.bat`，或打开 PowerShell：

```powershell
.\start_dev.bat
```

### Linux / macOS 用户

```bash
chmod +x start_dev.sh
./start_dev.sh
```

---

## 配置 API Key

### 方式一：密钥文件（推荐）

```bash
mkdir -p secrets
echo "your-glm-api-key" > secrets/glm_api_key
echo "your-deepseek-api-key" > secrets/deepseek_api_key
```

### 方式二：环境变量

```bash
# Windows PowerShell
$env:GLM_API_KEY="your-glm-key"
$env:DEEPSEEK_API_KEY="your-deepseek-key"

# Linux / macOS
export GLM_API_KEY="your-glm-key"
export DEEPSEEK_API_KEY="your-deepseek-key"

docker-compose run --rm dev
```

---

## 启动后的操作

进入 Docker 环境后，推荐进行 API 层测试：

```python
# 方式 1: API 冒烟测试（推荐）
python -c "
import asyncio
from api_client import capture_region_to_base64, process_multi_channel_ocr, translate_ocr_results

async def smoke_test():
    capture = capture_region_to_base64({'left': 0, 'top': 0, 'width': 800, 'height': 400})
    ocr = await process_multi_channel_ocr(capture)
    trans = await translate_ocr_results(ocr)
    print(trans)

asyncio.run(smoke_test())
"

# 方式 2: 进入 Python 交互式环境
python

# 方式 3: 运行测试脚本（若存在）
python docker_test.py
```

**不要在容器内运行 `python main.py` 期望看到 Overlay**——GUI 需在 Windows 本地安装 `requirements.txt` 后启动。

---

## 依赖说明

| 文件 | 用途 |
|------|------|
| `requirements.txt` | Windows 完整依赖（含 CustomTkinter、`pywin32`、`keyboard`） |
| `requirements-docker.txt` | 容器内 API 开发依赖（无 Windows UI 组件） |

Dockerfile 默认安装 `requirements-docker.txt`。

---

## 常用命令

```bash
docker-compose build
docker-compose run --rm dev
docker-compose down
docker-compose logs -f dev
```

---

## 注意事项

1. **GUI 功能**：CustomTkinter Overlay 仅支持 **Windows 10/11** 宿主机，纯 Docker 无法显示悬浮窗
2. **屏幕截图**：`mss` 在容器内无法截取宿主机游戏画面
3. **热键 / 鼠标穿透**：依赖 `keyboard` 与 `pywin32`，仅在 Windows 本地环境可用
4. **推荐用途**：API 测试、Prompt 调优、OCR/翻译链路验证、依赖隔离

---

## 开发者工作流

```bash
# 1. 克隆仓库
git clone <repo-url>
cd overwatch_translate_tool

# 2. 添加密钥
echo "api-key" > secrets/glm_api_key

# 3. 容器内开发 API 层
./start_dev.sh   # 或 start_dev.bat

# 4. Windows 宿主机联调 Overlay
pip install -r requirements.txt
python main.py

# 5. 提交代码
git commit && git push
```

---

协作者安装 Docker 即可获得一致的 **API 开发环境**；完整 Overlay 体验请在 Windows 本地配置 Python 虚拟环境。
