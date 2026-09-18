from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://pravburo:pravburo@shared_postgres:5432/pravburo"
    db_schema: str = "admin_panel"

    # ВАЖНО: тот же секрет, что и у сервисов-модулей (сейчас — leadreport_service),
    # чтобы токен, выданный здесь, принимался ими без повторного логина (единый вход для staff).
    jwt_secret: str = "dev-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 12

    # Refresh-токен живёт в httponly-куке (недоступен из JS, не светится в localStorage) —
    # фронт дёргает /auth/refresh при протухшем access_token вместо принудительного релогина.
    refresh_token_expires_days: int = 7
    # Secure-флаг куки — только когда сайт реально отдаётся по HTTPS (прод), иначе браузер
    # куку не примет и refresh не будет работать вообще.
    cookie_secure: bool = False


settings = Settings()
