from io import BytesIO

from minio import Minio
from minio.error import S3Error

from app.settings import Settings


class ObjectStorage:
    def __init__(self, settings: Settings) -> None:
        self.bucket = settings.minio_bucket
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    def ensure_bucket(self) -> None:
        try:
            if self.client.bucket_exists(self.bucket):
                return
            self.client.make_bucket(self.bucket)
        except S3Error:
            if not self.client.bucket_exists(self.bucket):
                raise

    def upload_jpeg(self, key: str, payload: bytes) -> None:
        self.client.put_object(
            self.bucket,
            key,
            BytesIO(payload),
            length=len(payload),
            content_type="image/jpeg",
        )
