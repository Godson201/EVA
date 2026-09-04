from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import Settings
from app.core.errors import AppError


class PrivateStorageMixin:
    _private_header = b"EVAE1"

    def _configure_encryption(self, secret: str):
        self._private_cipher = AESGCM(hashlib.sha256(secret.encode()).digest())

    async def put_private(self, key: str, content: bytes, content_type: str) -> str:
        nonce = os.urandom(12)
        encrypted = self._private_header + nonce + self._private_cipher.encrypt(nonce, content, key.encode())
        return await self.put(key, encrypted, "application/octet-stream")

    async def get_private(self, key: str) -> bytes:
        content = await self.get(key)
        if not content.startswith(self._private_header):
            return content  # Legacy compatibility until existing profiles are re-encrypted.
        nonce, encrypted = content[5:17], content[17:]
        return self._private_cipher.decrypt(nonce, encrypted, key.encode())


class LocalStorageService(PrivateStorageMixin):
    def __init__(self, root: str, secret: str = "eva-local-private-storage"):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._configure_encryption(secret)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise AppError("invalid_storage_key", "Invalid storage key", status_code=400)
        return path

    async def put(self, key: str, content: bytes, content_type: str) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, content)
        return key

    async def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise AppError("object_not_found", "Stored object not found", status_code=404)
        return await asyncio.to_thread(path.read_bytes)

    async def delete(self, key: str) -> None:
        path = self._path(key)
        if path.is_file():
            await asyncio.to_thread(path.unlink)


class S3StorageService(PrivateStorageMixin):
    def __init__(self, settings: Settings):
        import boto3
        if not settings.s3_bucket:
            raise ValueError("EVA_S3_BUCKET is required for S3 storage")
        self.bucket = settings.s3_bucket
        self._configure_encryption(settings.storage_encryption_key or settings.secret_key)
        self.client = boto3.client(
            "s3", endpoint_url=settings.s3_endpoint_url or None, region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id or None,
            aws_secret_access_key=settings.s3_secret_access_key or None,
        )

    async def put(self, key: str, content: bytes, content_type: str) -> str:
        await asyncio.to_thread(self.client.put_object, Bucket=self.bucket, Key=key, Body=content, ContentType=content_type)
        return key

    async def get(self, key: str) -> bytes:
        response = await asyncio.to_thread(self.client.get_object, Bucket=self.bucket, Key=key)
        return await asyncio.to_thread(response["Body"].read)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.client.delete_object, Bucket=self.bucket, Key=key)


def build_storage_service(settings: Settings):
    if settings.storage_backend == "local":
        return LocalStorageService(settings.storage_local_root, settings.storage_encryption_key or settings.secret_key)
    return S3StorageService(settings)
