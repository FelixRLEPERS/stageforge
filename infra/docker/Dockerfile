# StageForge runtime image.
# Hardware access (DeckLink, NDI, ToF) requires --device / --privileged
# at run time; this image is the software layer only.

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STAGEFORGE_LOG_LEVEL=info

WORKDIR /app

# System libs used by opencv-python at runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libgl1 \
       libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install --no-cache-dir .

COPY configs ./configs

RUN useradd --create-home --uid 10001 stageforge \
    && chown -R stageforge:stageforge /app
USER stageforge

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -m stageforge.orchestrator --help || exit 1

ENTRYPOINT ["python", "-m", "stageforge.orchestrator"]
CMD ["--config", "configs/dev.yaml"]
