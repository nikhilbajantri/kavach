FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LLM_PROVIDER=scripted KAVACH_DATA_DIR=/app/data

COPY pyproject.toml README.md ./
COPY kavach ./kavach
COPY mocks ./mocks
COPY agent ./agent
COPY bench ./bench
COPY policies ./policies
RUN pip install --no-cache-dir -e . && mkdir -p /app/data

EXPOSE 8000
CMD ["sh", "-c", "python -m mocks.seed && uvicorn kavach.api.main:app --host 0.0.0.0 --port 8000"]
