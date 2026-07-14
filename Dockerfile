FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    AUTOGEMATRIA_DATA_DIR=/data \
    AUTOGEMATRIA_VAR_DIR=/var/lib/autogematria

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src

RUN pip install --no-cache-dir . \
    && groupadd --system autogematria \
    && useradd --system --gid autogematria --home-dir /app autogematria \
    && mkdir -p /data /var/lib/autogematria \
    && chown -R autogematria:autogematria /app /var/lib/autogematria

USER autogematria

EXPOSE 8080
VOLUME ["/data", "/var/lib/autogematria"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/ready', timeout=3).read()"]

CMD ["python", "-m", "autogematria.tools.api_server"]
