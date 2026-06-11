#!/usr/bin/env bash
# OW-Light-Translator — 创建并初始化 Python 虚拟环境 (venv)
# 用法: ./scripts/setup_venv.sh
# 说明: Overlay GUI 仅 Windows 完整可用；本脚本主要用于 API 层依赖安装。

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/venv"
REQUIREMENTS="${PROJECT_ROOT}/requirements.txt"

cd "${PROJECT_ROOT}"

echo "OW-Light-Translator — 虚拟环境初始化"
echo "项目目录: ${PROJECT_ROOT}"
echo ""

PYTHON_CMD=""
for candidate in python3 python; do
    if command -v "${candidate}" >/dev/null 2>&1; then
        PYTHON_CMD="${candidate}"
        break
    fi
done

if [[ -z "${PYTHON_CMD}" ]]; then
    echo "错误: 未找到 Python 3.10+"
    exit 1
fi

VER="$("${PYTHON_CMD}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
MAJOR="${VER%%.*}"
MINOR="${VER#*.}"
if [[ "${MAJOR}" -lt 3 ]] || [[ "${MAJOR}" -eq 3 && "${MINOR}" -lt 10 ]]; then
    echo "错误: 需要 Python 3.10+，当前为 ${VER}"
    exit 1
fi

echo "使用 Python: ${PYTHON_CMD} (${VER})"

if [[ -d "${VENV_DIR}" ]]; then
    echo "检测到已有 venv 目录，跳过创建。"
else
    echo "正在创建虚拟环境: ${VENV_DIR}"
    "${PYTHON_CMD}" -m venv "${VENV_DIR}"
    echo "venv 创建完成。"
fi

VENV_PYTHON="${VENV_DIR}/bin/python"
VENV_PIP="${VENV_DIR}/bin/pip"

echo ""
echo "升级 pip..."
"${VENV_PYTHON}" -m pip install -U pip

echo "安装 requirements.txt..."
"${VENV_PIP}" install -r "${REQUIREMENTS}"

echo ""
echo "========================================"
echo "虚拟环境就绪。"
echo ""
echo "激活虚拟环境:"
echo "  source venv/bin/activate"
echo ""
echo "注意: venv/ 已在 .gitignore 中，请勿提交到 Git。"
echo "Overlay GUI 请在 Windows 宿主机运行 python main.py"
echo "========================================"
