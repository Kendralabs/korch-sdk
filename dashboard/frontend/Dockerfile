# Frontend image for the Korchestrator dashboard: static build served by nginx, which also
# reverse-proxies /api/* to the backend container so the browser never needs CORS or to know the
# backend's address directly. Build context is this directory (dashboard/frontend/).
#   docker build -t korchestrator-dashboard-frontend .

# --- Stage 1: build the Vite/React static assets ------------------------------------------------
FROM node:20-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Empty by default: same-origin requests to /api/* are proxied by nginx below. Override at build
# time (--build-arg VITE_API_BASE=https://api.example.com) only if the frontend is ever served
# from a different origin than the backend.
ARG VITE_API_BASE=""
ARG VITE_BEDROCK_MODEL="eu.anthropic.claude-sonnet-4-5-20250929-v1:0"
ENV VITE_API_BASE=$VITE_API_BASE
ENV VITE_BEDROCK_MODEL=$VITE_BEDROCK_MODEL
RUN npm run build

# --- Stage 2: serve the static build + proxy /api to the backend --------------------------------
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
# The official image's entrypoint envsubst's *.template files in this directory into conf.d at
# container start, substituting only real environment variables (nginx's own $host/$uri etc. are
# left alone). Default BACKEND_HOST matches docker-compose's service name; the ECS task definition
# overrides it to "localhost" since there both containers share one task's network namespace.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
ENV BACKEND_HOST=backend

EXPOSE 80
