# grokforge agents — Python service
FROM python:3.11-slim
WORKDIR /app

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# pyproject.toml references README.md, so it must be present at install time.
COPY pyproject.toml README.md /app/
COPY grokforge_agents /app/grokforge_agents
RUN pip install --no-cache-dir .

EXPOSE 8001
CMD ["uvicorn", "grokforge_agents.server:app", "--host", "0.0.0.0", "--port", "8001"]
