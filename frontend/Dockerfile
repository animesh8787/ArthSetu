# ArthSetu frontend image. Build context is the repo root — see
# docker-compose.yml.

FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend .
# Vite inlines VITE_* at build time, so sign-in config must arrive as build args.
ARG VITE_API_BASE_URL=
ARG VITE_FIREBASE_API_KEY=
ARG VITE_FIREBASE_AUTH_DOMAIN=
ARG VITE_FIREBASE_PROJECT_ID=
ARG VITE_FIREBASE_APP_ID=
ARG VITE_FIREBASE_AUTH_EMULATOR_HOST=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL     VITE_FIREBASE_API_KEY=$VITE_FIREBASE_API_KEY     VITE_FIREBASE_AUTH_DOMAIN=$VITE_FIREBASE_AUTH_DOMAIN     VITE_FIREBASE_PROJECT_ID=$VITE_FIREBASE_PROJECT_ID     VITE_FIREBASE_APP_ID=$VITE_FIREBASE_APP_ID     VITE_FIREBASE_AUTH_EMULATOR_HOST=$VITE_FIREBASE_AUTH_EMULATOR_HOST
RUN npm run build

# Unprivileged variant: runs as a non-root user out of the box, listens on
# 8080 instead of 80 (unprivileged ports).
FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1
