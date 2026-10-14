from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    internal_token: str = ""

    bitrix_profile_default_webhook_url: str = ""
    bitrix_profile_documents_webhook_url: str = ""
    bitrix_profile_messaging_webhook_url: str = ""
    bitrix_profile_consultation_webhook_url: str = ""

    # Optional embedded module. Disabled until explicitly configured.
    lead_phone_enabled: bool = False
    lead_phone_secret: str = ""
    lead_phone_profile: str = "consultation"
    lead_phone_from_type: str = "OTHER"
    lead_phone_to_type: str = "WORK"
    lead_contact_phone_field: str = "UF_CRM_68931B5269702"
    lead_contact_stage_id: str = "CONVERTED"
    lead_phone_allowed_sources: str = ""  # comma-separated SOURCE_ID; empty = all
    lead_phone_dry_run: bool = True
    lead_phone_max_attempts: int = Field(default=8, ge=1, le=20)
    lead_phone_retry_seconds: float = Field(default=2, ge=1, le=60)
    lead_phone_queue_path: str = "/data/lead_phone/jobs.sqlite3"

    @property
    def profile_webhook_urls(self) -> dict[str, str]:
        return {
            "default": self.bitrix_profile_default_webhook_url,
            "documents": self.bitrix_profile_documents_webhook_url,
            "messaging": self.bitrix_profile_messaging_webhook_url,
            "consultation": self.bitrix_profile_consultation_webhook_url,
        }


settings = Settings()
