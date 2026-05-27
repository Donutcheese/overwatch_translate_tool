#!/bin/bash
# OW-Light-Translator Docker 开发环境启动脚本

set -e

echo "🐳 OW-Light-Translator 开发环境"
echo "================================"

# 检查是否安装了 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ 错误: 未安装 Docker"
    echo "   请先安装 Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# 检查 docker-compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ 错误: 未安装 docker-compose"
    echo "   请先安装 docker-compose"
    exit 1
fi

# 创建 secrets 目录（如果不存在）
mkdir -p secrets

# 检查是否有 API Key
if [ ! -f secrets/glm_api_key ] && [ -z "$GLM_API_KEY" ]; then
    echo ""
    echo "⚠️  提示: 未检测到 API Key"
    echo "   请选择以下方式之一提供密钥："
    echo ""
    echo "   方式 1: 创建密钥文件"
    echo "   echo 'your-glm-key' > secrets/glm_api_key"
    echo "   echo 'your-deepseek-key' > secrets/deepseek_api_key"
    echo ""
    echo "   方式 2: 设置环境变量"
    echo "   export GLM_API_KEY='your-glm-key'"
    echo "   export DEEPSEEK_API_KEY='your-deepseek-key'"
    echo ""
    echo "   跳过密钥设置，继续启动..."
    echo ""
fi

# 构建并启动容器
echo "🔨 正在构建 Docker 镜像..."
docker-compose build

echo ""
echo "🚀 启动开发环境..."
echo ""

# 启动交互式开发环境
docker-compose run --rm dev
