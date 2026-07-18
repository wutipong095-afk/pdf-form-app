FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py license_core.py envutil.py logging_setup.py license_public.pem .
COPY fonts ./fonts
COPY templates ./templates
COPY demo ./demo
COPY static ./static

RUN mkdir -p /data/users \
    && useradd -m -u 10001 appuser \
    && chown -R appuser:appuser /app /data

ENV DATA_DIR=/data \
    HOST=0.0.0.0 \
    PORT=8000 \
    AUTH_REQUIRED=true \
    LOG_PER_WORKER=true \
    TRUST_X_FORWARDED_FOR=true \
    SESSION_COOKIE_SECURE=true

USER appuser
EXPOSE 8000

CMD ["gunicorn", "-b", "0.0.0.0:8000", "-w", "2", "--timeout", "120", "app:app"]
