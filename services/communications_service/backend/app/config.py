from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://communications:communications@postgres:5432/communications"
    db_schema: str = "communications"

    redis_url: str = "redis://redis:6379/0"

    bitrix_gateway_base_url: str = "http://host.docker.internal:8002"
    bitrix_gateway_token: str = ""
    bitrix_gateway_profile: str = "messaging"

    media_root: str = "/app/uploads"

    min_call_duration_seconds: int = 300
    bitrix_stat_poll_timeout_seconds: float = 400.0
    bitrix_stat_poll_interval_seconds: float = 10.0
    bitrix_comment_transcript_max_chars: int = 12000
    bitrix_comment_analysis_max_chars: int = 8000
    bitrix_lead_owner_type_id: str = "2"
    bitrix_contact_owner_type_id: str = "3"
    bitrix_owner_type_1_entity_type: str = "deal"
    bitrix_owner_type_2_entity_type: str = "lead"
    bitrix_owner_type_3_entity_type: str = "contact"
    bitrix_owner_type_4_entity_type: str = "company"
    allowed_crm_entity_types: str = ""

    transcription_provider: str = "openai_whisper"
    openai_api_key: str = ""
    openai_transcribe_model: str = "whisper-1"
    openai_transcribe_language: str = ""
    openai_diarization_model: str = "gpt-4o-mini"
    openai_analysis_model: str = "gpt-4o-mini"
    # Пусто по умолчанию: в монолите был захардкожен локальный SOCKS5 (Tor) на 127.0.0.1:9050,
    # что внутри контейнера уже не работает (127.0.0.1 = сам контейнер). Задайте явно при необходимости,
    # например socks5h://host.docker.internal:9050.
    openai_proxy_url: str = ""

    yandex_api_key: str = ""
    yandex_folder_id: str = ""
    yandex_stt_model: str = "deferred-general"
    yandex_stt_text_normalization: str = "TEXT_NORMALIZATION_ENABLED"
    yandex_stt_profanity_filter: bool = False
    yandex_stt_literature_text: bool = False
    yandex_stt_http_timeout_seconds: float = 60.0
    yandex_stt_poll_timeout_seconds: float = 1200.0
    yandex_stt_poll_interval_seconds: float = 2.0
    yandex_stt_return_partial_on_timeout: bool = True
    yandex_stt_trust_env: bool = False

    @property
    def owner_type_to_entity_type(self) -> dict[str, str]:
        return {
            "1": self.bitrix_owner_type_1_entity_type,
            "2": self.bitrix_owner_type_2_entity_type,
            "3": self.bitrix_owner_type_3_entity_type,
            "4": self.bitrix_owner_type_4_entity_type,
        }

    @property
    def allowed_crm_entity_types_set(self) -> set[str]:
        return {item.strip().upper() for item in self.allowed_crm_entity_types.split(",") if item.strip()}


settings = Settings()
