"""Private audio storage contract and local MinIO-compatible implementation."""

from pathlib import Path
from typing import Protocol


class PrivateObjectStorage(Protocol):
    def create_upload_url(self, key: str, content_type: str) -> str: ...
    def object_exists(self, key: str) -> bool: ...
    def object_size(self, key: str) -> int: ...
    def download_to(self, key: str, destination: Path) -> None: ...
    def create_download_url(self, key: str) -> str: ...
    def put_file(self, key: str, source: Path, content_type: str) -> None: ...
    def put_bytes(self, key: str, content: bytes, content_type: str) -> None: ...
    def open_download(self, key: str, byte_range: str | None = None) -> object: ...


class S3ObjectStorage:
    """Thin adapter around a provided S3-compatible client."""

    def __init__(self, client: object, bucket: str, public_client: object | None = None) -> None:
        self._client = client
        self._public_client = public_client or client
        self._bucket = bucket

    def create_upload_url(self, key: str, content_type: str) -> str:
        return self._public_client.generate_presigned_url(
            "put_object", Params={"Bucket": self._bucket, "Key": key, "ContentType": content_type}, ExpiresIn=300
        )

    def object_exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
        except Exception:
            return False
        return True

    def object_size(self, key: str) -> int:
        response = self._client.head_object(Bucket=self._bucket, Key=key)
        return int(response["ContentLength"])

    def download_to(self, key: str, destination: Path) -> None:
        self._client.download_file(self._bucket, key, str(destination))

    def create_download_url(self, key: str) -> str:
        return self._public_client.generate_presigned_url(
            "get_object", Params={"Bucket": self._bucket, "Key": key}, ExpiresIn=300
        )

    def put_file(self, key: str, source: Path, content_type: str) -> None:
        self._client.upload_file(
            str(source), self._bucket, key,
            ExtraArgs={"ContentType": content_type},
        )

    def put_bytes(self, key: str, content: bytes, content_type: str) -> None:
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
        )

    def open_download(self, key: str, byte_range: str | None = None) -> object:
        params = {"Bucket": self._bucket, "Key": key}
        if byte_range:
            params["Range"] = byte_range
        return self._client.get_object(**params)
