# One container serves both the API and the built web app (UI at /, API at /api).
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN  pip install --no-cache-dir -r backend/requirements.txt "psycopg[binary]"
COPY backend/ backend/
COPY eval/ eval/
COPY --from=web /web/dist frontend/dist
WORKDIR /app/backend
ENV PORT=8000 PYTHONUNBUFFERED=1
# One reverse proxy (the host's load balancer) sits in front of the app on Render/Cloud Run. Set to 2 if you add Cloudflare in front.
ENV TRUST_PROXY_HOPS=1
EXPOSE 8000
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --no-server-header
