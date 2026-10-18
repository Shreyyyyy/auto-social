# API + the whole reel pipeline: Python (FastAPI), ffmpeg, Remotion (headless Chrome), Claude Code CLI, uv/yt-dlp.
FROM node:22-bookworm-slim

# ffmpeg; the libraries Remotion's headless Chrome needs; fonts for Hindi + emoji; curl/certs for downloads
RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg ca-certificates curl lsof \
      libnss3 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libgbm1 libasound2 libxrandr2 libxkbcommon0 libxfixes3 \
      libxcomposite1 libxdamage1 libpango-1.0-0 libcairo2 libcups2 libdrm2 \
      fonts-noto-core fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

# uv (Python + yt-dlp via uvx) and the Claude Code CLI (research + scripts; needs CLAUDE_CODE_OAUTH_TOKEN)
COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /uvx /usr/local/bin/
RUN npm install -g @anthropic-ai/claude-code@2.1.286 && npm cache clean --force

ENV UV_PYTHON_INSTALL_DIR=/opt/python UV_CACHE_DIR=/tmp/uv-cache VIRTUAL_ENV=/opt/venv PATH=/opt/venv/bin:$PATH
RUN uv venv --python 3.12 /opt/venv && uv pip install --python /opt/venv/bin/python \
      fastapi uvicorn requests python-dotenv opencv-python-headless numpy pydantic anthropic edge-tts && chmod -R a+rwX /tmp/uv-cache

WORKDIR /app
# Remotion project: dependencies + its headless Chrome, baked into the image
COPY video/package.json video/package-lock.json video/
RUN cd video && npm ci --no-audit --no-fund && npx remotion browser ensure
COPY video/src video/src

COPY reel.py server.py competitors.py config.json ./
RUN mkdir -p out series research assets && chown -R node:node /app
USER node

ENV API_HOST=0.0.0.0 API_PORT=8787 PYTHONUNBUFFERED=1
EXPOSE 8787
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s CMD curl -fs http://127.0.0.1:8787/api/runs -o /dev/null || exit 1
CMD ["python", "server.py"]
