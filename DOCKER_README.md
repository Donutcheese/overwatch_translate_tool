# Docker 开发环境使用指南

## 🚀 快速开始

### Windows 用户

双击运行 `start_dev.bat`，或打开 PowerShell：

```powershell
.\start_dev.bat
```

### Linux/macOS 用户

```bash
chmod +x start_dev.sh
./start_dev.sh
```

---

## 🔑 配置 API Key

### 方式一：密钥文件（推荐）

```bash
# 创建 secrets 目录
mkdir -p secrets

# 添加你的密钥
echo "your-glm-api-key" > secrets/glm_api_key
echo "your-deepseek-api-key" > secrets/deepseek_api_key
```

### 方式二：环境变量

```bash
# Windows PowerShell
$env:GLM_API_KEY="your-glm-key"
$env:DEEPSEEK_API_KEY="your-deepseek-key"

# Linux/macOS
export GLM_API_KEY="your-glm-key"
export DEEPSEEK_API_KEY="your-deepseek-key"

# 然后启动
docker-compose run --rm dev
```

---

## 💻 启动后的操作

进入 Docker 环境后，你可以：

```python
# 方式 1: 直接运行主程序（需要 X11，显示 GUI）
python main.py

# 方式 2: 测试 API 功能
python -c "
import asyncio
from api_client import translate_ocr_results

results = asyncio.run(translate_ocr_results([
    {'text': 'HEAL ME', 'color_tag': {'label': 'Enemy'}}
]))
print(results)
"

# 方式 3: 进入 Python 交互式环境
python

# 方式 4: 运行测试
python docker_test.py
```

---

## 🛠️ 常用命令

```bash
# 构建镜像
docker-compose build

# 启动开发环境
docker-compose run --rm dev

# 退出并清理
exit

# 清理 Docker 资源
docker-compose down

# 查看日志
docker-compose logs -f dev
```

---

## ⚠️ 注意事项

1. **GUI 功能**：PyQt6 需要图形界面，纯 Docker 环境无法显示窗口
2. **屏幕截图**：mss 库在 Docker 中无法截取宿主机屏幕
3. **推荐用途**：API 测试、代码开发、依赖管理

---

## 📝 开发者工作流

```bash
# 1. 协作者克隆仓库
git clone <repo-url>
cd overwatch_translate_tool

# 2. 添加密钥
echo "api-key" > secrets/glm_api_key

# 3. 启动 Docker 开发环境
./start_dev.sh  # Linux/macOS
# 或
start_dev.bat   # Windows

# 4. 在容器中开发
# - 编辑代码（挂载卷会实时同步）
# - 运行测试
# - 提交代码

# 5. 退出容器
exit
```

---

现在协作者只需要安装 Docker，就能获得一致的开发环境，无需手动配置 Python！
