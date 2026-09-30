# Control-plane Python image. One image runs all three FastAPI services (browser API,
# agent API, private API) via different uvicorn commands in docker-compose.
FROM python:3.11-slim

WORKDIR /app

# LibreOffice headless converts the approved review docx -> PDF for protected client delivery
# (v2 Plan 3). soffice is invoked by common/pdf_deliver.py.
RUN apt-get update && apt-get install -y --no-install-recommends libreoffice-writer \
    && rm -rf /var/lib/apt/lists/*

# requirements.lock pins every direct and transitive version (from the image that passed the audit),
# so two builds of the same commit install the same code. Refresh it when you bump requirements.txt.
COPY controlplane/requirements.txt controlplane/requirements.lock ./
RUN pip install --no-cache-dir -r requirements.txt -c requirements.lock

COPY controlplane/ ./controlplane/

# Run as an unprivileged user. The data directories are created and owned here so a fresh named
# volume inherits the ownership. (A volume created by an older, root-run image needs a one-time
# chown: see DEPLOY.md.)
RUN useradd --create-home --uid 10001 varuna \
    && mkdir -p /dbdata /data/reports \
    && chown -R varuna:varuna /dbdata /data/reports /app
USER varuna

# Each module resolves its siblings via sys.path relative to its own location, so the
# per-service command just runs uvicorn from the api directory (set in compose).
WORKDIR /app/controlplane/api
