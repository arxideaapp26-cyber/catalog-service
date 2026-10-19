from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str = "products"
    minio_secure: bool = False
    bot_token: str = ""
    admin_ids: str = ""
    webapp_url: str = "http://localhost:3000"
    webhook_url: str = ""
    webhook_secret: str = ""

    model_config = SettingsConfigDict(extra="ignore")

    @property
    def admins(self) -> set[int]:
        result: set[int] = set()
        for part in self.admin_ids.split(","):
            value = part.strip()
            if value:
                result.add(int(value))
        return result
