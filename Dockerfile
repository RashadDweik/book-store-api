FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

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

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
