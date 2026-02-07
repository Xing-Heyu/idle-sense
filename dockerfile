FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# 修正：使用正确的 /health 端点（容器内使用127.0.0.1）
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import requests; r=requests.get('http://127.0.0.1:8000/health', timeout=2); exit(0 if r.status_code==200 else 1)"

CMD ["python", "scheduler/simple_server.py"]