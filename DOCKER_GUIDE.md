# Docker 使用指南

## ⚠️ 重要说明

本项目是 **Windows GUI 应用**，完整运行需要：
- 屏幕显示（PyQt6 GUI）
- 屏幕截图（mss 库）
- 全局热键（keyboard 库）
- Windows 特定 API

**Docker 运行环境有限制**，请根据需求选择合适的方案。

---

## 🐳 方案一：后端服务 Docker（推荐用于测试）

### 适用场景
- 测试 OCR 和翻译 API
- CI/CD 集成
- 验证代码逻辑

### 构建和运行

```bash
# 1. 复制环境变量模板
cp .env.docker .env

# 2. 编辑 .env 填入你的 API Key
vim .env

# 3. 构建镜像
docker build -t ow-translator:latest .

# 4. 运行容器
docker run -it --env-file .env ow-translator:latest python

# 5. 在 Python shell 中测试
>>> import asyncio
>>> from api_client import capture_region_to_base64, process_multi_channel_ocr, translate_ocr_results
>>> asyncio.run(translate_ocr_results([]))
```

### 或使用 docker-compose

```bash
# 启动后端服务
docker-compose up translator

# 后台运行
docker-compose up -d translator
```

---

## 🖥️ 方案二：GUI Docker（仅 Linux）

### 适用场景
- Linux 开发环境
- 无头服务器上的视觉测试

### 前提条件

Linux 系统需要 X11：

```bash
# Ubuntu/Debian
sudo apt install x11-apps x11-utils

# 允许 Docker 访问 X11
xhost +local:docker
```

### 构建和运行

```bash
# 构建 GUI 镜像
docker build -f Dockerfile.gui -t ow-translator-gui:latest .

# 运行 GUI 容器
docker run -it \
    --privileged \
    -e DISPLAY=$DISPLAY \
    -e XAUTHORITY=$XAUTHORITY \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -v $XAUTHORITY:/root/.Xauthority:ro \
    ow-translator-gui:latest
```

### 或使用 docker-compose

```bash
# 启动 GUI 模式
docker-compose up translator-gui
```

---

## 🪟 方案三：本地开发（推荐）

由于项目需要 Windows GUI，最佳方案是本地开发：

### Windows/macOS/Linux 本地开发

```bash
# 1. 克隆仓库
git clone <your-repo>
cd overwatch_translate_tool

# 2. 创建虚拟环境
python -m venv .venv

# 3. 激活虚拟环境
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# 4. 安装依赖
pip install -r requirements.txt

# 5. 配置 API Key
cp .env.docker local_api_keys.py
# 编辑 local_api_keys.py 填入你的 key

# 6. 运行
python main.py
```

---

## 🧪 测试 API 功能

无论哪种方案，都可以用以下方式测试后端：

```python
# test_api.py
import asyncio
from api_client import (
    capture_region_to_base64,
    process_multi_channel_ocr,
    translate_ocr_results
)

async def test_translation():
    # 模拟 OCR 结果（实际使用时从 capture_region_to_base64 获取）
    mock_ocr_results = [
        {"text": "HEAL ME", "color": "red"},
        {"text": "C9", "color": "blue"},
    ]

    # 测试翻译
    results = await translate_ocr_results(mock_ocr_results)
    for r in results:
        print(f"{r['source']} -> {r['translated']}")

asyncio.run(test_translation())
```

---

## 🔧 Docker 故障排除

### 问题：X11 连接被拒绝

```bash
# 解决方案
xhost +local:docker
```

### 问题：权限不足

```bash
# 解决方案（Linux）
sudo docker run ... --privileged
```

### 问题：找不到 display

```bash
# 检查 display
echo $DISPLAY

# 通常是 :0 或 :1
```

### 问题：API Key 未设置

```bash
# 确保 .env 文件存在且包含有效的 key
cat .env
```

---

## 📦 多平台构建（可选）

如果需要构建多平台镜像，使用 Docker Buildx：

```bash
# 启用 buildx
docker buildx create --use

# 构建多平台镜像
docker buildx build \
    --platform linux/amd64,linux/arm64 \
    -t yourusername/ow-translator:latest \
    --push .
```

---

## 🎯 总结

| 方案 | 平台 | GUI | 屏幕截图 | 热键 | 建议 |
|------|------|-----|----------|------|------|
| 后端 Docker | Linux | ❌ | ❌ | ❌ | API 测试 |
| GUI Docker | Linux + X11 | ✅ | ⚠️ 需特殊配置 | ⚠️ | 视觉测试 |
| 本地开发 | Windows/macOS/Linux | ✅ | ✅ | ✅ | **推荐** |

**建议：Docker 主要用于 CI/CD 和 API 测试，GUI 开发使用本地环境。**
