FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl \
  && rm -rf /var/lib/apt/lists/* \
  && useradd -m app
WORKDIR /srv
COPY pyproject.toml README.md* ./
COPY app ./app
COPY migrations ./migrations
COPY prompts ./prompts
COPY mcp_server.py ./
RUN pip install --no-cache-dir -e .
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/api/system/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
