# Control-plane Python image. One image runs all three FastAPI services (browser API,
# agent API, private API) via different uvicorn commands in docker-compose.
FROM python:3.11-slim

WORKDIR /app

# LibreOffice headless converts the approved review docx -> PDF for protected client delivery
# (v2 Plan 3). soffice is invoked by common/pdf_deliver.py.
RUN apt-get update && apt-get install -y --no-install-recommends libreoffice-writer \
    && rm -rf /var/lib/apt/lists/*

COPY controlplane/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY controlplane/ ./controlplane/

# Each module resolves its siblings via sys.path relative to its own location, so the
# per-service command just runs uvicorn from the api directory (set in compose).
WORKDIR /app/controlplane/api
