FROM node:22-alpine AS build
WORKDIR /src
COPY apps/staff-web/package*.json ./
COPY packages /packages
ARG NPM_REGISTRY=https://registry.npmmirror.com
RUN --mount=type=cache,target=/root/.npm npm config set registry "$NPM_REGISTRY" \
    && npm ci --prefer-offline --no-audit --fetch-retries=10 --fetch-timeout=600000
COPY apps/staff-web .
ENV REACT_APP_API_URL=/api
RUN npm run build
FROM nginx:1.27-alpine
COPY --from=build /src/build /usr/share/nginx/html
RUN printf 'server { listen 80; root /usr/share/nginx/html; index index.html; location / { try_files $uri $uri/ /index.html; } }' > /etc/nginx/conf.d/default.conf
