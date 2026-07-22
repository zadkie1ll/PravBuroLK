from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    internal_token: str = ""

    bitrix_profile_default_webhook_url: str = ""
    bitrix_profile_documents_webhook_url: str = ""
    bitrix_profile_messaging_webhook_url: str = ""

    @property
    def profile_webhook_urls(self) -> dict[str, str]:
        return {
            "default": self.bitrix_profile_default_webhook_url,
            "documents": self.bitrix_profile_documents_webhook_url,
            "messaging": self.bitrix_profile_messaging_webhook_url,
        }


settings = Settings()
