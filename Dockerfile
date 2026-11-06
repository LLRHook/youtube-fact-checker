FROM rust:1.93.1-slim-bookworm AS native-builder

WORKDIR /app
COPY native/ native/
RUN cargo build --locked --release --manifest-path native/Cargo.toml

FROM python:3.12-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim

WORKDIR /app
COPY --from=builder /install /usr/local

COPY backend/ backend/
COPY frontend/ frontend/
COPY --from=native-builder /app/native/target/release/libfactcheck_core.so backend/_native/libfactcheck_core.so

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["sh", "-c", "exec python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
