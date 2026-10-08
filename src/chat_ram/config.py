"""Configuração da aplicação, lida do ambiente / .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Conexão ao proxy LiteLLM, ao PostgreSQL 18 e parâmetros da Preparação."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    litellm_base_url: str
    litellm_api_key: str = "sk-local"
    model_alias: str

    postgres18_host: str = "127.0.0.1"
    postgres18_port: int = 5435
    postgres18_db: str = "otrs"
    postgres18_user: str = "otrs"
    postgres18_password: str = ""

    rag_schema: str = "rag"
    embedding_model: str = "Qwen/Qwen3-Embedding-0.6B"
    embedding_dimension: int = 1024
    embedding_dimensions: int | None = None
    embedding_batch: int = 64
    trecho_max_chars: int = 2000
    trecho_overlap_chars: int = 200
    processing_version: int = 1
