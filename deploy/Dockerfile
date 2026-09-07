# syntax=docker/dockerfile:1
# Berth 的單一容器 image（plan §1.1、§9.1）。build context 是 repo 根目錄：
#   docker build -f deploy/Dockerfile -t ghcr.io/1morr/berth:latest .

# --- 前端：產出靜態檔，node 不進 runtime ---
FROM node:24-slim AS web

ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
WORKDIR /src/web

RUN corepack enable

COPY web/package.json web/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY web/ ./
RUN pnpm build

# --- 後端：把 venv 建在最終路徑上，shebang 才不會指到 build 階段的位置 ---
FROM python:3.13-slim AS backend

COPY --from=ghcr.io/astral-sh/uv:0.12.2 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /src

# 先只裝相依：改 berth/ 的程式碼不會讓這一層失效。
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# README 與 LICENSE 是 build wheel 的輸入（pyproject 的 readme / license-files）。
COPY README.md LICENSE ./
COPY berth/ ./berth/
RUN uv sync --locked --no-dev --no-editable

# --- runtime ---
FROM python:3.13-slim AS runtime

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    CONFIG_ROOT=/config \
    DATA_ROOT=/data \
    WEB_ROOT=/app/web \
    PORT=8383 \
    PUID=1000 \
    PGID=1000 \
    UMASK=022

# 入口腳本會把這個使用者對到 PUID / PGID；1000 只是還沒設定時的預設。
RUN groupadd --gid 1000 berth \
    && useradd --uid 1000 --gid berth --home-dir /app --no-create-home --shell /usr/sbin/nologin berth \
    && mkdir -p /config /data

COPY --from=backend /app/.venv /app/.venv
COPY --from=web /src/web/dist /app/web
COPY --chmod=0755 deploy/entrypoint.sh /usr/local/bin/berth-entrypoint

EXPOSE 8383

# image 內沒有 curl，用 venv 的 python 打自己的健康端點就夠了。
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.environ['PORT']+'/api/health').read()"

ENTRYPOINT ["/usr/local/bin/berth-entrypoint"]
CMD ["berth", "serve"]
