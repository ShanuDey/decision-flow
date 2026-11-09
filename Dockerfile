# syntax=docker/dockerfile:1
# One image runs both the API (uvicorn, :8000) and the web app (Next.js standalone, :3000).

FROM node:24-slim AS web-build
WORKDIR /src/web
RUN npm install -g pnpm@12.18.0
COPY web/package.json web/pnpm-lock.yaml web/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY web/ .
# Inlined into the browser bundle at build time: must be the URL the *browser* uses.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN pnpm build

FROM python:3.12-slim AS api-build
COPY --from=ghcr.io/astral-sh/uv:0.11.15 /uv /usr/local/bin/uv
WORKDIR /srv/api
COPY api/pyproject.toml api/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim
COPY --from=node:24-slim /usr/local/bin/node /usr/local/bin/node
RUN useradd --system --no-create-home app
WORKDIR /srv/api
# Same base image as api-build, so the venv's interpreter path is still valid here.
COPY --from=api-build /srv/api/.venv .venv
COPY api/ .
COPY --from=web-build --chown=app:app /src/web/.next/standalone /srv/web
COPY --from=web-build --chown=app:app /src/web/.next/static /srv/web/.next/static
COPY --from=web-build --chown=app:app /src/web/public /srv/web/public
COPY docker/entrypoint.sh /srv/entrypoint.sh
USER app
ENV PATH="/srv/api/.venv/bin:$PATH" NODE_ENV=production
EXPOSE 8000 3000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5   CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8000/health'); u.urlopen('http://localhost:3000/')"
CMD ["bash", "/srv/entrypoint.sh"]
