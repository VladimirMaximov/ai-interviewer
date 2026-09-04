"""Create a synthetic local invitation and the private MinIO bucket."""

from uuid import uuid4

import boto3
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.services.hiring_context import HiringContextService

engine = create_engine(settings.database_url)
client = boto3.client(
    "s3",
    endpoint_url=settings.s3_endpoint_url,
    aws_access_key_id=settings.s3_access_key,
    aws_secret_access_key=settings.s3_secret_key,
)
try:
    client.head_bucket(Bucket=settings.s3_bucket)
except Exception:
    client.create_bucket(Bucket=settings.s3_bucket)
with Session(engine) as db:
    service = HiringContextService(db)
    vacancy = service.create_vacancy(
        title="Synthetic Python backend developer",
        document=(
            "Synthetic vacancy. Required: Python, FastAPI, PostgreSQL. "
            "No real candidate or company data."
        ).encode(),
        filename="synthetic-vacancy.txt",
        media_type="text/plain",
        actor_id="demo-recruiter",
        idempotency_key=f"demo-vacancy-{uuid4()}",
    )
    invitation = service.create_invitation(
        vacancy_id=vacancy.id,
        actor_id="demo-recruiter",
        candidate_alias="synthetic-candidate",
        expires_in_hours=24,
    )
print(f"vacancy_id={vacancy.id}")
print(f"http://localhost:5173/?token={invitation.candidate_token}")
