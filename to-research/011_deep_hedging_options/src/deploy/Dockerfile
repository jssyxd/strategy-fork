# watch-video Docker image
# Runs watch-video as a CLI tool against a mounted video/output directory.
#
# Build:
#   docker build -t watch-video .
#
# Run (local file):
#   docker run --rm \
#     -v /path/to/video.mp4:/data/video.mp4:ro \
#     -v /path/to/output:/data/out \
#     watch-video /data/video.mp4 --out /data/out
#
# Run (URL — internet access required inside container):
#   docker run --rm \
#     -v /path/to/output:/data/out \
#     watch-video https://www.loom.com/share/XXX --out /data/out

FROM python:3.11-slim

# ---------- system deps ----------
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        tesseract-ocr \
        tesseract-ocr-chi-sim \
        tesseract-ocr-eng \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

# ---------- uv (fast pip replacement used by watch-video's shebang) ----------
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# ---------- get the watch-video script ----------
# Option A (default): clone directly from GitHub — fully self-contained.
# Option B: if building from a local clone that already contains the `watch-video`
#            file, comment out the RUN below and uncomment the COPY line instead.
WORKDIR /app
ARG WATCH_VIDEO_REF=main
RUN git clone --depth 1 --branch ${WATCH_VIDEO_REF} \
        https://github.com/WebDevBar/watch-video /app/watch-video-repo \
    && cp /app/watch-video-repo/watch-video /app/watch-video \
    && rm -rf /app/watch-video-repo \
    && chmod +x /app/watch-video
# COPY watch-video /app/watch-video  # ← uncomment for local-clone builds

# Pre-install inline script deps via uv so the container is self-contained.
# uv resolves the `# dependencies = [...]` block inside the script.
RUN uv run --script /app/watch-video --help > /dev/null 2>&1 || true

# ---------- whisper model pre-download (optional; reduces cold-start) ----------
# Remove the ARG/RUN block below to skip model caching and save ~500 MB image size.
# The model is downloaded to ~/.cache/huggingface/hub on first real run otherwise.
ARG WHISPER_MODEL=small
ENV WHISPER_MODEL=${WHISPER_MODEL}
RUN python3 - <<'EOF'
import os
try:
    from faster_whisper import WhisperModel
    model_name = os.environ.get("WHISPER_MODEL", "small")
    WhisperModel(model_name, device="cpu", compute_type="int8")
    print(f"[docker build] Whisper model '{model_name}' cached.")
except Exception as e:
    print(f"[docker build] Whisper pre-cache skipped: {e}")
EOF

# ---------- runtime ----------
WORKDIR /data
ENTRYPOINT ["uv", "run", "--script", "/app/watch-video"]
CMD ["--help"]
