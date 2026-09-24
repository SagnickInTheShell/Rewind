FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend
# CPU torch by default; the GPU compose profile overrides TORCH_INDEX.
ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu
COPY backend/pyproject.toml ./
ENV UV_HTTP_TIMEOUT=300
RUN pip install uv && mkdir -p rewind && touch rewind/__init__.py \
    && uv pip install --system torch torchvision --index-url ${TORCH_INDEX} \
    && uv pip install --system -e ".[dev,perf]"
COPY backend/ ./
COPY scripts/ /app/scripts/

ENV REWIND__APP__DATA_DIR=/app/data
EXPOSE 8000
CMD ["uvicorn", "rewind.main:app", "--host", "0.0.0.0", "--port", "8000"]
