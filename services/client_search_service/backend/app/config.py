from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://pravburo:pravburo@shared_postgres:5432/pravburo"
    db_schema: str = "client_search"

    jwt_secret: str = "dev-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"

    # Ссылка "Списания клиента" — client_withdrawals пока не вынесен, ведёт прямо в монолит.
    monolith_client_withdrawals_url: str = "https://prav-buro.ru/client-withdrawals"

    # internal-эндпоинт монолита для "Общий хвост по снятиям"
    # (client_withdrawals/views.py:internal_client_tail_amount) — сам модуль пока не вынесен,
    # это единственная точка чтения без переноса всего client_withdrawals.
    monolith_internal_base_url: str = "https://prav-buro.ru"
    monolith_internal_token: str = ""

    bitrix_deal_base_url: str = "https://prav-buro.bitrix24.ru/crm/deal/details"


settings = Settings()
