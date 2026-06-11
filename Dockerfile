FROM python:3.12-slim

WORKDIR /app

# OpenCV 运行时依赖（headless API 测试）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Docker 环境仅安装 API 层依赖（不含 pywin32 / CustomTkinter Overlay）
COPY requirements-docker.txt .

RUN pip install --no-cache-dir -r requirements-docker.txt

COPY . .

ENV PYTHONUNBUFFERED=1

# 默认进入交互式 Python；完整 GUI 请在 Windows 宿主机运行 python main.py
CMD ["python"]
