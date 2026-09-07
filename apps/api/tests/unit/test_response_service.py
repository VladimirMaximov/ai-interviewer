import unittest
from concurrent.futures import Executor, Future
from pathlib import Path
from uuid import uuid4

from app.services.response_service import ResponseService, UploadNotFoundError


class ImmediateExecutor(Executor):
    def submit(self, fn, /, *args, **kwargs):
        future = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except BaseException as error:
            future.set_exception(error)
        return future


class FakeStorage:
    def __init__(self, exists: bool = True) -> None:
        self.exists = exists
        self.downloaded_to: Path | None = None

    def object_exists(self, _: str) -> bool:
        return self.exists

    def download_to(self, _: str, destination: Path) -> None:
        self.downloaded_to = destination
        destination.write_bytes(b"synthetic audio")


class FakeStore:
    def __init__(self) -> None:
        self.events: list[tuple[str, str | None]] = []

    def set_transcription_processing(self, _: object) -> None:
        self.events.append(("processing", None))

    def set_transcription_completed(self, _: object, transcript: str) -> None:
        self.events.append(("completed", transcript))

    def set_transcription_failed(self, _: object) -> None:
        self.events.append(("failed", None))


class FakeTranscriber:
    def __init__(self, result: str = "Синтетический ответ", fails: bool = False) -> None:
        self.result = result
        self.fails = fails

    def transcribe(self, source_path: Path, *, language: str = "ru") -> str:
        if self.fails:
            raise RuntimeError("model unavailable")
        if not source_path.is_file() or language != "ru":
            raise AssertionError("invalid transcription input")
        return self.result


class ResponseServiceTests(unittest.TestCase):
    def test_confirmed_upload_transcribes_and_persists_text(self) -> None:
        storage, store = FakeStorage(), FakeStore()
        service = ResponseService(storage, store, FakeTranscriber(), executor=ImmediateExecutor())

        service.confirm_upload(uuid4(), "responses/example.webm").result()

        self.assertEqual(store.events, [("processing", None), ("completed", "Синтетический ответ")])
        self.assertIsNotNone(storage.downloaded_to)
        self.assertFalse(storage.downloaded_to.exists())

    def test_failed_transcription_never_persists_partial_text(self) -> None:
        store = FakeStore()
        service = ResponseService(FakeStorage(), store, FakeTranscriber(fails=True), executor=ImmediateExecutor())

        service.confirm_upload(uuid4(), "responses/example.webm").result()

        self.assertEqual(store.events, [("processing", None), ("failed", None)])

    def test_missing_object_is_not_queued(self) -> None:
        store = FakeStore()
        service = ResponseService(FakeStorage(exists=False), store, FakeTranscriber(), executor=ImmediateExecutor())

        with self.assertRaises(UploadNotFoundError):
            service.confirm_upload(uuid4(), "responses/missing.webm")
        self.assertEqual(store.events, [])
