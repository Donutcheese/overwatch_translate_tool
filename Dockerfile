FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for opencv and screen capture
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libxkbcommon0 \
    libgbm1 \
    libnotify4 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install PyQt6 system bindings (for Linux Docker - no actual GUI)
RUN pip install --no-cache-dir PyQt6

# Copy application code
COPY . .

# Set environment variables
ENV DISPLAY=:99
ENV QT_QPA_PLATFORM=offscreen
ENV PYTHONUNBUFFERED=1

# Expose any ports if needed (for future HTTP server)
EXPOSE 8000

# Default command - runs the backend service test
CMD ["python", "-c", "import asyncio; from api_client import capture_region_to_base64, process_multi_channel_ocr, translate_ocr_results; print('OW-Light-Translator Docker ready. Import modules to test API services.')"]
