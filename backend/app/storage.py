"""Private certificate storage in MinIO. Only metadata lives in Postgres."""
import io
import os
import uuid
from datetime import timedelta

from fastapi import HTTPException
from minio import Minio

from .config import (MAX_UPLOAD_BYTES, MINIO_ACCESS_KEY, MINIO_BUCKET, MINIO_ENDPOINT,
                     MINIO_PUBLIC_ENDPOINT, MINIO_SECRET_KEY, MINIO_PUBLIC_SECURE, MINIO_SECURE, SIGNED_URL_SECONDS)

ALLOWED = {
    ".pdf": ("application/pdf", b"%PDF"),
    ".jpg": ("image/jpeg", b"\xff\xd8\xff"),
    ".jpeg": ("image/jpeg", b"\xff\xd8\xff"),
    ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
}
PHOTO_TYPES = {"image/jpeg", "image/png"}

_client: Minio | None = None
_public: Minio | None = None


def client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, secure=MINIO_SECURE, region="us-east-1")
    return _client


def _public_client() -> Minio:
    # Same credentials, browser-reachable host. Presigning is local computation (region fixed), no network call.
    global _public
    if _public is None:
        _public = Minio(MINIO_PUBLIC_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, secure=MINIO_PUBLIC_SECURE, region="us-east-1")
    return _public


def ensure_bucket() -> None:
    c = client()
    if not c.bucket_exists(MINIO_BUCKET):
        c.make_bucket(MINIO_BUCKET)      # buckets are private by default; no public policy is ever set


def validate_upload(filename: str, content_type: str | None, data: bytes, photo: bool = False) -> tuple[str, str]:
    """Returns (extension, mime). Checks extension, declared MIME, size and file signature."""
    if not data:
        raise HTTPException(422, "The uploaded file is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 5 MB")
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in ALLOWED:
        raise HTTPException(422, "Only PDF, JPG and PNG files are allowed")
    mime, magic = ALLOWED[ext]
    if content_type != mime:
        raise HTTPException(422, "File type does not match its extension")
    if not data.startswith(magic):
        raise HTTPException(422, "File content does not match its type")
    if photo and mime not in PHOTO_TYPES:
        raise HTTPException(422, "Photos must be JPG or PNG")
    return ext, mime


def put(student_id, submission_id, ext: str, mime: str, data: bytes) -> str:
    key = f"students/{student_id}/submissions/{submission_id}/{uuid.uuid4().hex}{ext}"  # never the user's file name
    client().put_object(MINIO_BUCKET, key, io.BytesIO(data), len(data), content_type=mime)
    return key


def signed_url(key: str) -> str:
    return _public_client().presigned_get_object(MINIO_BUCKET, key, expires=timedelta(seconds=SIGNED_URL_SECONDS))


def remove(key: str) -> None:
    client().remove_object(MINIO_BUCKET, key)
