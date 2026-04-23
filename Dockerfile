FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y git && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY agent/ ./agent/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir aider-chat python-dotenv

RUN mkdir -p /app/code /app/agent/tasks

WORKDIR /app

# Добавляем /app в PYTHONPATH чтобы Python мог найти модуль agent
ENV PYTHONPATH=/app

CMD ["python", "-m", "agent.agent"]
