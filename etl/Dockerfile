FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# The pipeline needs only httpx (also pinned in backend/requirements.txt).
RUN pip install "httpx>=0.27"

COPY . ./etl

# Run only when started with the "etl" profile (see docker-compose.yml).
CMD ["python", "-m", "etl.downloader"]
