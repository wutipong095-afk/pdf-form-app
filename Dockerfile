FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py backup_core.py envutil.py fields_core.py form_store.py formdd_io.py \
     history_core.py i18n_core.py job_core.py library_core.py license_core.py \
     logging_setup.py profiles_core.py sheet_core.py update_core.py workdir_core.py \
     license_public.pem .
COPY fonts ./fonts
COPY locales ./locales
COPY templates ./templates
COPY demo ./demo
COPY formpacks ./formpacks
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
