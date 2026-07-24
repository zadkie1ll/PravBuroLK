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

    contract_file_field: str = "UF_CRM_1745892619372"
    contract_link_field: str = "UF_CRM_1775217002"
    contract_number_field: str = "UF_CRM_1745892727271"
    contract_second_payment_field: str = "UF_CRM_1745841297007"
    contract_accepted_field: str = "UF_CRM_1775216196958"
    contract_first_payment_field: str = "UF_CRM_1742468532579"

    template_path: str = "/app/templates_src/template_2.docx"
    output_dir: str = "/app/generated_docs"

    # Шаг B: страница подтверждения/оплаты договора, теперь хостится этим сервисом.
    alfa_api_url_prod: str = ""
    alfa_user_prod: str = ""
    alfa_pass_prod: str = ""

    contract_payment_recipient: str = "СВИРИДЕНКО СТАНИСЛАВ ВАЛЕРЬЕВИЧ (ИП)"
    contract_payment_inn: str = "616706684677"
    contract_payment_kpp: str = ""
    contract_payment_address: str = ""
    contract_payment_currency: str = "RUR"
    contract_payment_bank: str = 'ФИЛИАЛ "РОСТОВСКИЙ" АО "АЛЬФА-БАНК"'
    contract_payment_bik: str = "046015207"
    contract_payment_account: str = "40802810426340008508"
    contract_payment_corr_account: str = "30101810500000000207"
    contract_payment_qr_path: str = ""

    # Публичный адрес, по которому клиент открывает эту страницу (для returnUrl/failUrl Альфа-Банка).
    public_base_url: str = "http://localhost:8005"


settings = Settings()
