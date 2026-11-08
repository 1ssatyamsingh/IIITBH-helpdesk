from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "IIITBH RAG API"
    app_env: str = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"
    frontend_origins: str = "http://localhost:5173"
    max_upload_files: int = 20
    max_upload_mb: int = 50
    max_upload_batch_mb: int = 200
    data_dir: Path = Path(__file__).resolve().parents[2] / "data"
    pdf_min_text_characters_per_page: int = 30
    chunk_size: int = 1200
    chunk_overlap: int = 200

    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    qdrant_collection: str = "iiitbh_knowledge"
    qdrant_distance: str = "Cosine"

    embedding_provider: str = "local"
    embedding_model_id: str = "Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0"
    local_embedding_base_url: str | None = "http://127.0.0.1:8088"
    cloudflare_account_id: str | None = None
    cloudflare_api_token: str | None = None
    cloudflare_embedding_model_id: str = "@cf/qwen/qwen3-embedding-0.6b"
    embedding_dimension: int = 1024
    embedding_batch_size: int = 8

    groq_api_key: str | None = None
    groq_vlm_model: str = "qwen/qwen3.8-27b"
    groq_render_dpi: int = 144
    groq_max_image_mb: int = 18

    answer_model_provider: str | None = None
    answer_model_base_url: str | None = None
    answer_model_id: str | None = None
    answer_model_api_key: str | None = None

    web_search_enabled: bool = True
    web_search_max_results: int = 6

    @field_validator("frontend_origins")
    @classmethod
    def validate_frontend_origins(cls, value: str) -> str:
        origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        if not origins:
            raise ValueError("At least one explicit frontend origin must be configured.")
        if "*" in origins:
            raise ValueError("Wildcard CORS origins are not allowed when credentials are enabled.")
        for origin in origins:
            if origin == "null" or not origin.startswith(("http://", "https://")):
                raise ValueError("Frontend origins must be explicit HTTP(S) origins.")
        return ",".join(dict.fromkeys(origins))

    @property
    def resolved_embedding_model_id(self) -> str:
        if self.embedding_provider.strip().lower() == "cloudflare":
            return self.cloudflare_embedding_model_id
        return self.embedding_model_id

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
