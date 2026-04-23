FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y git && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY aider/ ./aider/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir aider-chat python-dotenv

RUN mkdir -p /app/code /app/aider/tasks

WORKDIR /app

ENTRYPOINT ["python", "aider/agent.py"]
