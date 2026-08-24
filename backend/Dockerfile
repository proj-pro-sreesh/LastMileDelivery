FROM python:3.14-slim

WORKDIR /srv/app

# Install dependencies first so Docker layer caching works between code changes.
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts

EXPOSE 8000

# Alembic reads its URL from app settings via env vars (see app/core/config.py),
# so migrations apply cleanly against the compose database service.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
