FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY deploy/backend.requirements.txt /tmp/backend.requirements.txt
RUN pip install --no-cache-dir -r /tmp/backend.requirements.txt

COPY backend /app/backend

CMD ["uvicorn", "--app-dir", "backend/src", "lsl.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers"]

