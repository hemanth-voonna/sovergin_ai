FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata \
    ANONYMIZED_TELEMETRY=False

# Tesseract for OCR + basic system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-hin \
        tesseract-ocr-mar \
        poppler-utils \
        curl \
        && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Non-root runtime user (defense in depth)
RUN useradd -m -u 1001 sovereign && mkdir -p /app/data && chown -R sovereign:sovereign /app/data /app

# Pre-download the ONNX embedding model (as the runtime user, so the cache is
# actually found at startup) — makes first boot fast and offline-capable
USER sovereign
RUN python -c "from chromadb.utils.embedding_functions import DefaultEmbeddingFunction; fn = DefaultEmbeddingFunction(); fn(['sovereignai warm-up'])"

COPY . .

# COPY runs as root; hand ownership of the code + data back to the runtime user
USER root
RUN chown -R sovereign:sovereign /app/data /app
USER sovereign

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]