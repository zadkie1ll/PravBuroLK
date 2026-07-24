from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bitrix_gateway_base_url: str = "http://host.docker.internal:8002"
    bitrix_gateway_token: str = ""
    bitrix_gateway_profile: str = "documents"

    # Должен совпадать с DJANGO_SECRET_KEY монолита — Шаг B (страница подтверждения/оплаты
    # договора) пока живёт в монолите, а токен для неё генерирует уже этот сервис. Подпись
    # обязана быть байт-в-байт совместима с django.core.signing.Signer (см. app/services/django_signing.py).
    django_secret_key: str = "django-insecure-dev-key"
    contract_page_sign_salt: str = "documents.contract.confirmation"

    # Пока Шаг B не вынесен, ссылка на страницу подтверждения строится на монолит.
    monolith_base_url: str = "http://host.docker.internal:8000"

    contract_file_field: str = "UF_CRM_1745892619372"
    contract_link_field: str = "UF_CRM_1775217002"
    contract_number_field: str = "UF_CRM_1745892727271"
    contract_second_payment_field: str = "UF_CRM_1745841297007"

    template_path: str = "/app/templates_src/template_2.docx"
    output_dir: str = "/app/generated_docs"


settings = Settings()
