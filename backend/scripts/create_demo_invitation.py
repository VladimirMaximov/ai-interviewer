"""Create a synthetic local invitation and the private MinIO bucket."""
from datetime import datetime, timedelta, timezone
import sys
import boto3
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.config import settings
from app.models.interview import InterviewInvitation
from app.security.invitations import create_invitation_secret, digest_invitation_secret

engine = create_engine(settings.database_url)
client = boto3.client("s3", endpoint_url=settings.s3_endpoint_url, aws_access_key_id=settings.s3_access_key, aws_secret_access_key=settings.s3_secret_key)
try:
    client.head_bucket(Bucket=settings.s3_bucket)
except Exception:
    client.create_bucket(Bucket=settings.s3_bucket)
secret = create_invitation_secret()
with Session(engine) as db:
    db.add(InterviewInvitation(token_digest=digest_invitation_secret(secret), expires_at=datetime.now(timezone.utc) + timedelta(days=1)))
    db.commit()
print(f"http://localhost:5173/?token={secret}")
