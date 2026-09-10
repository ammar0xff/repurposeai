"""Centralized configuration. Validated at startup. Env-driven."""
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    database_url: str = Field(default="sqlite:///./data/repurposeai.db")
    storage_path: str = "./data"
    storage_backend: str = "local"

    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"

    whisper_model: str = "small"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"

    llm_provider: str = "heuristic"
    llm_base_url: str = ""
    llm_model: str = "gpt-oss-20b"
    llm_api_key: str = ""
    ollama_base_url: str = "http://127.0.0.1:11434"

    max_upload_mb: int = 2048
    max_concurrent_jobs: int = 2
    cors_origins: str = "http://localhost:5173,http://localhost:8000"
    auth_token: str = ""
    port: int = 8000

    @field_validator("storage_backend")
    @classmethod
    def _backend(cls, v: str) -> str:
        if v not in ("local", "s3"):
            raise ValueError("STORAGE_BACKEND must be local|s3")
        return v

    @field_validator("llm_provider")
    @classmethod
    def _provider(cls, v: str) -> str:
        if v not in ("heuristic", "openai_compat", "ollama", "local"):
            raise ValueError("LLM_PROVIDER must be heuristic|openai_compat|ollama|local")
        return v

    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
