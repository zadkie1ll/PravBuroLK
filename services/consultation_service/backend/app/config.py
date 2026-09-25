from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bitrix_gateway_base_url: str = "http://host.docker.internal:8002"
    bitrix_gateway_token: str = ""
    bitrix_gateway_profile: str = "consultation"

    # Свой секрет для подписи ссылок на отчёт — не обязан совпадать с монолитом
    # (в отличие от documents_service, эта страница никогда не жила в Django).
    token_secret_key: str = "consultation-insecure-dev-key"
    token_sign_salt: str = "consultation.report"

    # Публичный адрес, по которому фронтенд открывает клиент/менеджер.
    public_base_url: str = "http://localhost:5180"

    # Откуда backend (Playwright) берёт тот же фронтенд для рендера в PDF —
    # см. deploy-заметки: в проде это localhost (network_mode: host), в докер-дев —
    # имя контейнера на общей сети.
    print_base_url: str = "http://frontend:5180"

    # ── Поля сделки Bitrix ──────────────────────────────────────────────────
    # Подтверждены реальным продовым кодом монолита (bitrix/views.py:
    # build_consultation, generate_template.py) по сделке 16778 — это тот же
    # набор данных, что уже используется для старого (некрасивого) варианта
    # отчёта, просто рендерим их в новом дизайне.
    field_client_name: str = "TITLE"
    field_consultation_date: str = "DATE_CREATE"

    field_property: str = "UF_CRM_1754647601622"
    field_income: str = "UF_CRM_1770129399154"  # числовая зарплата (UF_SALARY в монолите), не AI-описание дохода
    field_transactions: str = "UF_CRM_1754647663541"
    field_marriage: str = "UF_CRM_1754647902223"
    field_children: str = "UF_CRM_1754647671862"
    field_contract_status: str = "UF_CRM_1745888352245"

    field_debt: str = "UF_CRM_1746616466655"
    field_cost: str = "OPPORTUNITY"  # стандартное поле суммы сделки
    field_installment: str = "UF_CRM_1784121569198"

    # Этих полей пока нет в Bitrix вообще (ни в старой AI-легенде, ни в build_consultation) —
    # заводим здесь плейсхолдерами, чтобы форма и дизайн были готовы уже сейчас. Пока
    # реальных ID нет, значения не будут доходить до Bitrix при сохранении (неизвестное
    # поле). Когда поля заведут в Bitrix — просто подставить их код в .env, без правок кода.
    field_priority: str = "UF_CRM_TODO_PRIORITY"
    field_summary: str = "UF_CRM_TODO_SUMMARY"
    field_current_payment: str = "UF_CRM_TODO_CURRENT_PAYMENT"
    field_included: str = "UF_CRM_TODO_INCLUDED"
    field_extra: str = "UF_CRM_TODO_EXTRA"
    field_next_step: str = "UF_CRM_TODO_NEXT_STEP"
    field_next_date: str = "UF_CRM_TODO_NEXT_DATE"
    field_documents: str = "UF_CRM_TODO_DOCUMENTS"

    # "Срок рассрочки" / "Первый платёж и дата" / "Итого по графику" — переиспользуем
    # поля договорного флоу (documents_service), которые пишет бот/менеджер при
    # оформлении договора, а не эта форма — поэтому не редактируются на этой странице.
    field_installment_months: str = "UF_CRM_1742480133860"  # количество платежей
    field_first_payment_amount: str = "UF_CRM_1742468532579"
    field_first_payment_date: str = "UF_CRM_1742468566169"
    field_bonus_amount: str = "UF_CRM_1742457114242"  # "сумма бонус|RUB" — для расчёта "Итого по графику"
    field_discount_amount: str = "UF_CRM_1742457148727"  # "скидка|RUB"

    # Файл — переиспользуем то же поле, куда старый (некрасивый) генератор в монолите
    # уже кладёт этот PDF (bitrix/views.py: build_consultation), тот же смысл поля,
    # просто теперь в новом дизайне. Ссылки на страницу отчёта раньше не было вообще
    # (старый флоу просто отдавал PDF роботу как HTTP-ответ) — это поле нужно завести.
    field_report_file: str = "UF_CRM_1770371897876"
    field_report_link: str = "UF_CRM_TODO_REPORT_LINK"

    # ── Статические (не по сделке) данные ──────────────────────────────────
    support_chat_url: str = "https://t.me/+0cxGWcMqMPY2Yzky"
    telegram_url: str = "https://t.me/pravburo"
    vk_url: str = "https://vk.com/bankrotstvo.life"
    youtube_url: str = ""
    yandex_maps_url: str = "https://yandex.ru/profile/7626506757"

    # Если задано — сгенерированный PDF дополнительно сохраняется локально по этому
    # пути (для локальной проверки рендера без реального похода в Bitrix). Пусто —
    # поведение по умолчанию, ничего локально не пишем.
    debug_pdf_output_path: str = ""


settings = Settings()
