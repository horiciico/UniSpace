FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# The ETL uses the backend's models and database settings, so it is built from the
# repo root (context ".") with the backend code and requirements copied in.
COPY backend/requirements.txt backend/requirements-dev.txt ./
RUN pip install -r requirements-dev.txt

COPY backend/ ./
COPY etl/ ./etl/

# Migrations first (D-002), then the pipeline. Extra arguments (for example
# `--faculty sti`) are passed to the pipeline. Run only with the "etl" profile.
ENTRYPOINT ["sh", "-c", "alembic upgrade head && python -m etl.schedule.downloader \"$@\"", "etl"]
