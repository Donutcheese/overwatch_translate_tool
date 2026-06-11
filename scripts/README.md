# scripts/ - 虚拟环境安装脚本

本目录提供 **venv 初始化脚本**（提交到 Git）。虚拟环境目录 **`venv/`** 由用户本地创建，已在根目录 `.gitignore` 中忽略。

## Windows（推荐）

```powershell
# 方式 1: 双击
scripts\setup_venv.bat

# 方式 2: PowerShell
.\scripts\setup_venv.ps1

# 激活
.\venv\Scripts\Activate.ps1

# 或快速激活
. .\scripts\activate_venv.ps1
```

## Linux / macOS

```bash
chmod +x scripts/setup_venv.sh
./scripts/setup_venv.sh
source venv/bin/activate
```

## 脚本说明

| 文件 | 作用 |
|------|------|
| `setup_venv.ps1` | 创建 `venv/`、升级 pip、安装 `requirements.txt`、运行 pywin32 后置安装 |
| `setup_venv.bat` | Windows 双击入口，调用 `setup_venv.ps1` |
| `setup_venv.sh` | Linux/macOS 创建 venv（Overlay GUI 仍需 Windows） |
| `activate_venv.ps1` | 在已存在 venv 时快速激活 |
| `generate_icon.py` | 从 `img/icon.png` 生成 `img/icon.ico` |
| `build.ps1` / `build.bat` | PyInstaller 打包 exe（含应用图标） |

## 注意

- 需要 **Python 3.10+**
- 不要将 `venv/` 目录提交到 Git
- Overlay 完整功能请在 Windows 宿主机运行 `python main.py`

## 打包 exe

```powershell
.\scripts\build.bat
# 输出: dist\OW-Color-Fluent-Translator.exe
```
