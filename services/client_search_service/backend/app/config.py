from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://pravburo:pravburo@shared_postgres:5432/pravburo"
    db_schema: str = "client_search"

    jwt_secret: str = "dev-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"

    bitrix_deal_base_url: str = "https://prav-buro.bitrix24.ru/crm/deal/details"

    # bitrix_gateway_service — используется для синка "Списания клиента" в Bitrix
    # (crm.deal.update, порт client_withdrawals/services.py:sync_withdrawals_to_bitrix)
    # теперь, когда withdrawal_records живут в этом сервисе, а не в монолите.
    bitrix_gateway_base_url: str = "http://host.docker.internal:8002"
    bitrix_gateway_token: str = ""
    bitrix_gateway_profile: str = "default"

    # Ссылка на страницу списаний для поля в Bitrix — теперь это страница в собственном
    # фронтенде сервиса, не в монолите. Placeholder-порт для локальной разработки — на
    # проде должен указывать на реальный домен фронтенда после cutover.
    withdrawals_page_base_url: str = "http://localhost:5177"
    bitrix_client_withdrawals_link_field: str = "UF_CRM_1774516783"
    bitrix_client_withdrawals_field: str = "UF_CRM_1774516806"


settings = Settings()
