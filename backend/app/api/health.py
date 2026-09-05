"""Liveness and dependency-aware readiness endpoints."""

import subprocess
from importlib.util import find_spec
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text

from app.config import settings

router = APIRouter(tags=["health"])


def readiness() -> dict[str, str]:
    checks: dict[str, str] = {}
    try:
        with create_engine(settings.database_url, pool_pre_ping=True).connect() as db:
            db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"
    try:
        import boto3
        boto3.client("s3", endpoint_url=settings.s3_endpoint_url, aws_access_key_id=settings.s3_access_key, aws_secret_access_key=settings.s3_secret_key).head_bucket(Bucket=settings.s3_bucket)
        checks["object_storage"] = "ok"
    except Exception:
        checks["object_storage"] = "unavailable"
    try:
        import redis
        checks["redis"] = "ok" if redis.Redis.from_url(settings.redis_url).ping() else "unavailable"
    except Exception:
        checks["redis"] = "unavailable"
    if settings.presenter_enabled:
        gpu = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], capture_output=True, timeout=5, check=False)
        checks["cuda"] = "ok" if gpu.returncode == 0 else "unavailable"
        checks["musetalk"] = "ok" if Path(settings.presenter_musetalk_root).is_dir() else "unavailable"
        checks["portrait"] = "ok" if Path(settings.presenter_portrait_path).is_file() else "unavailable"
        checks["xtts"] = "ok" if find_spec("TTS") is not None else "unavailable"
    else:
        checks.update(cuda="disabled", musetalk="disabled", portrait="disabled", xtts="disabled")
    return checks


@router.get("/health")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready(_: Request) -> JSONResponse:
    checks = readiness()
    healthy = all(value in {"ok", "disabled"} for value in checks.values())
    return JSONResponse(status_code=200 if healthy else 503, content={"status": "ready" if healthy else "degraded", "checks": checks})
