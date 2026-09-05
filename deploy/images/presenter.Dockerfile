FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 MPLBACKEND=Agg COQUI_TOS_AGREED=1
RUN sed -i 's|http://archive.ubuntu.com/ubuntu|https://mirror.selectel.ru/ubuntu|g; s|http://security.ubuntu.com/ubuntu|https://mirror.selectel.ru/ubuntu|g' /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends python3.10 python3-pip ffmpeg git \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY deploy/images/presenter-requirements.txt /tmp/presenter-requirements.txt
RUN python3.10 -m pip install --no-cache-dir --upgrade 'pip<25' 'setuptools<70' wheel \
    && python3.10 -m pip install --no-cache-dir \
       torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 \
       --index-url https://download.pytorch.org/whl/cu118 \
    && python3.10 -m pip install --no-cache-dir --no-build-isolation 'chumpy==0.70' \
    && python3.10 -m pip install --no-cache-dir -r /tmp/presenter-requirements.txt
COPY backend/pyproject.toml /app/pyproject.toml
COPY backend/app /app/app
RUN python3.10 -m pip install --no-cache-dir '.[workers]'
