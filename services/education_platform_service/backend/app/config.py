from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = (
        "postgresql+psycopg2://education_platform:education_platform@postgres:5432/education_platform"
    )
    db_schema: str = "education_platform"

    jwt_secret: str = "dev-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 12

    # Примонтированный private_media монолита (BASE_DIR/private_media), read-only.
    media_root: str = "/private_media"


settings = Settings()
