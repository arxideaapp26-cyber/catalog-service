from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str = "products"
    minio_secure: bool = False
    public_api_url: str = "http://localhost:8000"

    model_config = SettingsConfigDict(extra="ignore")

    @property
    def public_base(self) -> str:
        return self.public_api_url.rstrip("/")
