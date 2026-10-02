FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/app/data \
    VAR_DIR=/app/var

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-deps .

COPY data ./data
COPY eval ./eval
COPY scripts ./scripts

RUN useradd --create-home app && mkdir -p /app/var && chown app /app/var
USER app

EXPOSE 8741
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8741/health')"
CMD ["uvicorn", "review_assistant.api:app", "--host", "0.0.0.0", "--port", "8741"]
