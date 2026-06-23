from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mistral_api_key: str = Field(default="", alias="MISTRAL_API_KEY")
    mistral_base_url: str = Field(default="https://api.mistral.ai/v1", alias="MISTRAL_BASE_URL")
    mistral_model: str = Field(default="mistral-medium-latest", alias="MISTRAL_MODEL")
    default_library_name: str = Field(default="Halfords Annual Report RAG", alias="DEFAULT_LIBRARY_NAME")
    halfords_report_url: str = Field(default="", alias="HALFORDS_REPORT_URL")
    data_dir: str = Field(default="data", alias="DATA_DIR")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
