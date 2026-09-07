"""Pre-render private animated question MP4s from a local portrait and XTTS.

The CPU fallback blends closed/open-mouth portrait keyframes while speech plays.
A neural lip-sync renderer can later replace only ``render_video`` while keeping
the same storage/API contract.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import wave
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import boto3
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.interview import AvatarAssetStatus, InterviewInvitation, QuestionAvatarAsset
from app.security.invitations import digest_invitation_secret


def synthesize(text: str, destination: Path) -> None:
    request = Request(
        f"{settings.xtts_endpoint.rstrip('/')}/synthesize",
        data=json.dumps({"text": text, "speaker": settings.xtts_voice}).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urlopen(request, timeout=60) as response:
        destination.write_bytes(response.read())


def render_video(portrait: Path, speaking_portrait: Path, audio: Path, destination: Path) -> int:
    """Compose transparent portrait keyframes over a neutral background.

    The blend is intentionally limited to two identity-preserving keyframes. It
    gives a modest speaking motion on CPU without pretending to be phoneme-level
    lip synchronisation.
    """
    with wave.open(str(audio), "rb") as wav:
        duration_seconds = wav.getnframes() / wav.getframerate()
    subprocess.run([
        settings.ffmpeg_binary, "-nostdin", "-y",
        "-loop", "1", "-i", str(portrait),
        "-loop", "1", "-i", str(speaking_portrait),
        "-i", str(audio),
        "-filter_complex",
        (
            "[0:v]scale=360:640:force_original_aspect_ratio=decrease,"
            "pad=360:640:(ow-iw)/2:(oh-ih)/2:color=0x17191d,format=rgba[closed];"
            "[1:v]scale=360:640:force_original_aspect_ratio=decrease,"
            "pad=360:640:(ow-iw)/2:(oh-ih)/2:color=0x17191d,format=rgba[open];"
            "[closed][open]hstack=inputs=2,crop=360:640:'mod(n,2)*360':0,fps=12,format=yuv420p[v]"
        ),
        "-map", "[v]", "-map", "2:a", "-t", f"{duration_seconds:.3f}",
        "-r", "12", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "25",
        "-pix_fmt", "yuv420p", "-c:a", "aac", str(destination),
    ], check=True, capture_output=True, text=True)
    probe = subprocess.run([settings.ffmpeg_binary, "-i", str(destination)], capture_output=True, text=True)
    # The exact duration is not essential for the fallback; UI uses ended event.
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True)
    args = parser.parse_args()
    portrait = Path("apps/api/assets/avatar/interviewer-cutout.png")
    speaking_portrait = Path("apps/api/assets/avatar/interviewer-speaking-cutout.png")
    if not portrait.is_file() or not speaking_portrait.is_file():
        raise SystemExit("Missing local avatar portrait keyframes")
    db = Session(create_engine(settings.database_url))
    invitation = db.scalar(select(InterviewInvitation).where(InterviewInvitation.token_digest == digest_invitation_secret(args.token)))
    if not invitation:
        raise SystemExit("Invitation not found")
    from app.interview_config import invitation_input
    interview = invitation_input(invitation.question_config, invitation.follow_up_after_all_answers)
    client = boto3.client("s3", endpoint_url=settings.s3_endpoint_url, aws_access_key_id=settings.s3_access_key, aws_secret_access_key=settings.s3_secret_key)
    for question in interview.questions:
        asset = db.scalar(select(QuestionAvatarAsset).where(QuestionAvatarAsset.invitation_id == invitation.id, QuestionAvatarAsset.question_id == question.id))
        if not asset:
            asset = QuestionAvatarAsset(invitation_id=invitation.id, question_id=question.id, renderer="keyframe_blend_xtts", status=AvatarAssetStatus.PROCESSING, created_at=datetime.now(timezone.utc))
            db.add(asset); db.commit(); db.refresh(asset)
        try:
            with tempfile.TemporaryDirectory(prefix="ai-interviewer-avatar-") as directory:
                root = Path(directory); audio = root / "question.wav"; video = root / "question.mp4"
                synthesize(question.text, audio); render_video(portrait, speaking_portrait, audio, video)
                key = f"avatar/{invitation.id}/{question.id}.mp4"
                client.upload_file(str(video), settings.s3_bucket, key, ExtraArgs={"ContentType": "video/mp4"})
            asset.renderer, asset.status, asset.video_storage_key, asset.failure_reason = "keyframe_blend_xtts", AvatarAssetStatus.READY, key, None
        except Exception as error:
            asset.status, asset.failure_reason = AvatarAssetStatus.FAILED, str(error)[:2000]
        db.commit()
    print("Avatar assets rendered")


if __name__ == "__main__":
    main()
