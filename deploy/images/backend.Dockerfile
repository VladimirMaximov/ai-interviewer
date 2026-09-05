FROM python:3.12-slim
RUN sed -i 's|http://deb.debian.org/debian-security|https://mirror.selectel.ru/debian-security|g; s|http://deb.debian.org/debian|https://mirror.selectel.ru/debian|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/pyproject.toml /app/pyproject.toml
COPY backend/app /app/app
RUN pip install --no-cache-dir '.[workers]'
COPY backend/alembic.ini /app/alembic.ini
COPY backend/alembic /app/alembic
COPY backend/scripts /app/scripts
