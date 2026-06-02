FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./

RUN pip install --no-cache-dir --upgrade pip \
    && python - <<'PY'
import subprocess
import sys
import tomllib

with open("pyproject.toml", "rb") as handle:
    data = tomllib.load(handle)

for_dep = data.get("project", {}).get("dependencies", [])
if for_dep:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--no-cache-dir", *for_dep])
PY

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY scripts ./scripts

RUN chmod +x /app/scripts/docker-start.sh

CMD ["/app/scripts/docker-start.sh"]
