FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip first
RUN pip install --upgrade pip

# Install packages in stages to avoid conflicts
RUN pip install --no-cache-dir numpy==1.26.4
RUN pip install --no-cache-dir openai-whisper==20231117
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Copy requirements and install rest
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]