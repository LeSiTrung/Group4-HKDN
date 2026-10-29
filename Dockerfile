FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/opt/venv/bin:$PATH"
RUN python -m venv /opt/venv
COPY backend/requirements.txt /tmp/requirements.txt
RUN /opt/venv/bin/python -m pip install --no-cache-dir -r /tmp/requirements.txt
RUN useradd --uid 10001 --create-home app && mkdir -p /var/lib/d7 && chown app:app /var/lib/d7
WORKDIR /app/backend
COPY --chown=app:app backend/app ./app
COPY --chown=app:app data/faq /app/data/faq
COPY --chown=app:app scripts/restore.py /app/scripts/restore.py
COPY --from=frontend --chown=app:app /build/dist /app/frontend/dist
USER app
ENV DATA_DIR=/var/lib/d7
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-proxy-headers", "--no-access-log"]
