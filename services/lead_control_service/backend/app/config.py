from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://pravburo:pravburo@shared_postgres:5432/pravburo"
    db_schema: str = "lead_control"

    redis_url: str = "redis://redis:6379/0"

    bitrix_gateway_base_url: str = "http://host.docker.internal:8002"
    bitrix_gateway_token: str = ""
    bitrix_gateway_profile: str = "default"

    # Внутренний токен для эндпоинтов, которые вызывает монолит (webhook приёма сделки,
    # дублирование сделки в "Агенты" — раньше это был прямой Python-импорт из clients/views.py).
    internal_api_token: str = ""

    lead_control_disable_field: str = "UF_CRM_1774361781838"
    lead_control_moderator_field: str = "UF_CRM_1774359191"
    lead_control_task_description_field: str = "UF_CRM_1758727134167"

    lead_control_monitored_stages: str = "NEW,UC_EXAMPLE_STAGE"

    lead_control_typical_task_title: str = "Связаться с клиентом"
    lead_control_typical_task_description: str = "Необходимо повторно связаться с клиентом по сделке."
    lead_control_moderator_task_title: str = "Проверить ситуацию клиента"
    lead_control_moderator_task_description: str = "Проверить текущую ситуацию клиента по сделке."
    lead_control_moderator_task_creator_id: int = 444
    lead_control_moderator_task_every_days: int = 3
    lead_control_sales_deal_category_id: int = 2

    lead_control_workday_start_hour: int = 10
    lead_control_workday_end_hour: int = 19

    deal_duplication_source_category_id: int = 2
    deal_duplication_source_won_stage_id: str = "C2:WON"
    deal_duplication_target_category_id: int = 10
    deal_duplication_target_first_stage_id: str = "C10:NEW"

    bitrix_deal_base_url: str = "https://prav-buro.bitrix24.ru/crm/deal/details"

    @property
    def monitored_stages_set(self) -> set[str]:
        return {s.strip() for s in self.lead_control_monitored_stages.split(",") if s.strip()}


settings = Settings()
