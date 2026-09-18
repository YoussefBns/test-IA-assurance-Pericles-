# Même version de Python que l'entraînement ; aucun RAG ni GPU dans cette image.
FROM python:3.13.5-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CHURN_LOG_DIR=/app/logs \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1

WORKDIR /app
COPY requirements-api.txt ./
RUN python -m pip install --no-cache-dir -r requirements-api.txt \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

COPY partie1_ml/__init__.py partie1_ml/features.py partie1_ml/model.joblib partie1_ml/metadata.json partie1_ml/drift_reference.json ./partie1_ml/
COPY partie3_mlops/__init__.py partie3_mlops/app.py partie3_mlops/schemas.py partie3_mlops/monitoring.py ./partie3_mlops/
RUN mkdir -p /app/logs && chown -R app:app /app/logs
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"
CMD ["python", "-m", "uvicorn", "partie3_mlops.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
