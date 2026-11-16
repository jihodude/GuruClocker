# guruclocker in a box: Python, ffmpeg, Whisper speech-to-text and the code, preinstalled.
# On a PC with an NVIDIA GPU, run with --gpus all (windows.bat does this automatically).
FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    HF_HOME=/cache/huggingface \
    HF_HUB_VERBOSITY=error \
    GURUCLOCKER_IN_DOCKER=1 \
    OUTPUT_DIR=/app/output

WORKDIR /app

# Dependencies first (cached layer), then the code.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY guruclocker ./guruclocker
COPY .env.example ./
RUN uv sync --frozen --no-dev

# CUDA libraries installed by pip (only present in the x86_64 image) need to be on the loader path.
ENV PATH=/app/.venv/bin:$PATH \
    LD_LIBRARY_PATH=/app/.venv/lib/python3.11/site-packages/nvidia/cublas/lib:/app/.venv/lib/python3.11/site-packages/nvidia/cudnn/lib

VOLUME ["/app/output", "/cache"]
ENTRYPOINT ["python", "-m", "guruclocker"]
