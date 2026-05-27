@echo off
REM OW-Light-Translator Docker 开发环境启动脚本 (Windows)

echo 🐳 OW-Light-Translator 开发环境
echo =================================

REM 检查 Docker
docker version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: 未安装 Docker
    echo    请先安装 Docker: https://docs.docker.com/get-docker/
    pause
    exit /b 1
)

REM 创建 secrets 目录
if not exist secrets mkdir secrets

REM 检查 API Key
if not exist secrets\glm_api_key (
    echo.
    echo ⚠️  提示: 未检测到 API Key
    echo    请创建密钥文件:
    echo    echo your-glm-key ^> secrets\glm_api_key
    echo    echo your-deepseek-key ^> secrets\deepseek_api_key
    echo.
    echo    跳过密钥设置，继续启动...
    echo.
)

REM 构建并启动
echo 🔨 正在构建 Docker 镜像...
docker-compose build

echo.
echo 🚀 启动开发环境...
echo.

docker-compose run --rm dev

pause
