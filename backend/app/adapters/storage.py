"""Private audio storage contract and local MinIO-compatible implementation."""

from pathlib import Path
from typing import Protocol


class PrivateObjectStorage(Protocol):
    def create_upload_url(self, key: str, content_type: str) -> str: ...
    def object_exists(self, key: str) -> bool: ...
    def download_to(self, key: str, destination: Path) -> None: ...


class S3ObjectStorage:
    """Thin adapter around a provided S3-compatible client."""

    def __init__(self, client: object, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def create_upload_url(self, key: str, content_type: str) -> str:
        return self._client.generate_presigned_url(
            "put_object", Params={"Bucket": self._bucket, "Key": key, "ContentType": content_type}, ExpiresIn=300
        )

    def object_exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
        except Exception:
            return False
        return True

    def download_to(self, key: str, destination: Path) -> None:
        self._client.download_file(self._bucket, key, str(destination))
