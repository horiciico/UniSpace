FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dev image: includes test tools (requirements-dev.txt pulls in requirements.txt).
# Built from the repo root (context "."): the admin's data import runs the pipelines in etl/.
COPY backend/requirements.txt backend/requirements-dev.txt ./
RUN pip install -r requirements-dev.txt

COPY backend/ ./
# Outside /app, so the dev mount of backend/ does not hide it and the checks of app/ skip it.
COPY etl/ /opt/etl/etl/
ENV PYTHONPATH=/opt/etl

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
