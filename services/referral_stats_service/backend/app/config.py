from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://pravburo:pravburo@shared_postgres:5432/pravburo"
    db_schema: str = "referral_stats"

    jwt_secret: str = "dev-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"

    # Реферальные ссылки строятся так же, как Client.get_ref_link/Employee.get_ref_link
    # в монолите (reverse("referral_landing", args=[referral_code])) — здесь просто
    # собираем абсолютный URL на публичном сайте монолита вручную.
    site_base_url: str = "https://prav-buro.ru"


settings = Settings()
