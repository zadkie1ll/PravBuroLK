from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://pravburo:pravburo@shared_postgres:5432/pravburo"
    db_schema: str = "urlshorter"

    # ВАЖНО: тот же секрет, что у admin_panel_service — токен, выданный там для staff,
    # должен без повторного логина проходить require_staff здесь (единый вход из хаба).
    jwt_secret: str = "dev-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"

    # Домен, на котором реально висит публичный редирект /go (основной сайт, а не
    # панель админки). Ссылки создаются через запросы, пришедшие с разных хостов
    # (panel.prav-buro.ru, localhost и т.д.), поэтому публичный URL нельзя строить
    # из request.base_url — он должен быть фиксированным.
    public_redirect_base_url: str = "https://prav-buro.ru"


settings = Settings()
