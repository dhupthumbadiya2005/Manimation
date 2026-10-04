# One container: FastAPI backend + render toolchain + the built React UI.

FROM node:22-slim AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
# Manim native deps (cairo/pango), video/audio (ffmpeg, sox), and LaTeX for MathTex.
# ~460 MB of packages: downloads are retried and kept in a BuildKit cache, so a
# build interrupted by the network resumes instead of starting over.
RUN rm -f /etc/apt/apt.conf.d/docker-clean \
    && echo 'Acquire::Retries "5"; Acquire::http::Timeout "60";' > /etc/apt/apt.conf.d/80-retries
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
        build-essential pkg-config libcairo2-dev libpango1.0-dev \
        ffmpeg sox libsox-fmt-mp3 \
        texlive texlive-latex-extra texlive-fonts-recommended texlive-science \
        cm-super dvisvgm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/ ./
COPY --from=ui /ui/dist /app/frontend/dist

ENV PATH="/app/backend/.venv/bin:$PATH" \
    PYTHONPATH=/app/backend \
    MANIMATION_DATA_DIR=/app/data \
    MANIMATION_TTS=gtts
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
