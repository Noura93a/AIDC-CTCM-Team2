FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/model_cache \
    TRANSFORMERS_CACHE=/model_cache

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-venv python3-pip \
    libreoffice \
    poppler-utils \
    tesseract-ocr tesseract-ocr-ara \
    libgl1 libglib2.0-0 \
    wget curl git \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

WORKDIR /app

RUN pip install --no-cache-dir \
    torch==2.5.1 --index-url https://download.pytorch.org/whl/cu121

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

COPY data/hrsd_data_ai_taxonomy.csv /data/hrsd_data_ai_taxonomy.csv
COPY data/Golden-set-Reviewed.xlsx /data/Golden-set-Reviewed.xlsx

HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=120s \
    CMD python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]