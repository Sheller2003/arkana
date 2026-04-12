FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/app \
    XDG_DATA_HOME=/app/.local/share \
    PYTHON_KEYRING_BACKEND=keyrings.alt.file.PlaintextKeyring

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends docker.io \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/.local/share/python_keyring

COPY src ./src
COPY pyproject.toml .
COPY mysql_arkana_setup.sql .
COPY sql ./sql
COPY scripts ./scripts

EXPOSE 8000

CMD ["uvicorn", "src.arkana_api_service.app:app", "--host", "0.0.0.0", "--port", "8000"]
