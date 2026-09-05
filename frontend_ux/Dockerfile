FROM node:22-alpine AS build
WORKDIR /src
COPY frontend_ux/package*.json ./
COPY packages /packages
RUN npm ci
COPY frontend_ux .
ENV REACT_APP_API_URL=/api
RUN npm run build
FROM nginx:1.27-alpine
COPY --from=build /src/build /usr/share/nginx/html
RUN printf 'server { listen 80; root /usr/share/nginx/html; index index.html; location / { try_files $uri $uri/ /index.html; } }' > /etc/nginx/conf.d/default.conf
