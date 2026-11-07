FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 APP_DATABASE_PATH=/data/app.sqlite3
WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --upgrade pip && python -m pip install -r requirements.txt

ARG SOURCE_REPOSITORY=https://github.com/mahsonpro-design/albayda_court.git
ARG SOURCE_REF=main
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && git clone --depth 1 --branch ${SOURCE_REF} ${SOURCE_REPOSITORY} /tmp/court-source \
    && cp /tmp/court-source/case_records.py /app/ \
    && cp /tmp/court-source/sultan-medium.ttf /app/ \
    && cp /tmp/court-source/*.pdf /app/ \
    && rm -rf /tmp/court-source /var/lib/apt/lists/*

COPY api.py ./
RUN mkdir -p /data && useradd --system --uid 10001 --create-home appuser && chown -R appuser:appuser /app /data
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]
