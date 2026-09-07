import tempfile
import unittest
import wave
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.domain.interview_runtime import PresenterAssetRequest
from app.models.interview import AvatarAssetStatus, QuestionAvatarAsset
from app.services.presenter_assets import CeleryPresenterDispatcher, PresenterAssetService


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_file(self, key: str, source: Path, content_type: str) -> None:
        self.objects[key] = source.read_bytes()


class FakeTts:
    def synthesize(self, text: str, *, speaker: str, output_path: Path) -> Path:
        with wave.open(str(output_path), "wb") as output:
            output.setnchannels(1); output.setsampwidth(2); output.setframerate(24_000)
            output.writeframes(b"\0\0" * 100)
        return output_path


class FakeAvatar:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def render(self, portrait: Path, audio: Path, *, output_path: Path, workspace: Path) -> Path:
        if self.fail:
            raise RuntimeError("synthetic renderer failure")
        output_path.write_bytes(b"synthetic mp4")
        return output_path


class PresenterRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite://")
        QuestionAvatarAsset.__table__.create(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        self.storage = MemoryStorage()

    def tearDown(self) -> None:
        self.engine.dispose()

    def request(self) -> PresenterAssetRequest:
        return PresenterAssetRequest(
            invitation_id=uuid4(), question_id=uuid4(),
            question_text="Объясните PostgreSQL", voice_id="demo",
            portrait_version="v1", renderer_version="musetalk-v1.5",
        )

    def test_prewarm_enqueue_is_deduplicated(self) -> None:
        service = PresenterAssetService(self.sessions, self.storage, FakeTts(), FakeAvatar())
        enqueued: list[str] = []
        dispatcher = CeleryPresenterDispatcher(
            service, voice_id="demo", renderer_version="v1",
            task_sender=enqueued.append,
        )
        request = self.request()
        dispatcher.enqueue(request.invitation_id, request.question_id, request.question_text)
        dispatcher.enqueue(request.invitation_id, request.question_id, request.question_text)
        self.assertEqual(len(enqueued), 1)
        with self.sessions() as db:
            self.assertEqual(len(list(db.scalars(select(QuestionAvatarAsset)))), 1)

    def test_avatar_failure_preserves_generated_audio_for_static_fallback(self) -> None:
        service = PresenterAssetService(self.sessions, self.storage, FakeTts(), FakeAvatar(fail=True))
        asset = service.ensure(self.request())
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RuntimeError):
                service.process(asset.id, Path(directory) / "portrait.png")
        with self.sessions() as db:
            stored = db.get(QuestionAvatarAsset, asset.id)
            self.assertEqual(stored.status, AvatarAssetStatus.FAILED)
            self.assertEqual(stored.failure_stage, "avatar")
            self.assertIsNotNone(stored.audio_storage_key)
            self.assertIn(stored.audio_storage_key, self.storage.objects)


if __name__ == "__main__":
    unittest.main()
