"""Configuração da aplicação, lida do ambiente / .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Conexão ao proxy LiteLLM, ao PostgreSQL 18 e parâmetros da Preparação."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    litellm_base_url: str
    litellm_api_key: str = "sk-local"
    model_alias: str

    # Chave exigida nos endpoints /v1/* (vazio = sem autenticação).
    chat_ram_api_key: str | None = None

    # Guardrail de escopo (palavras-chave + classificador). Desligue para economizar.
    guardrail_escopo: bool = True

    postgres18_host: str = "127.0.0.1"
    postgres18_port: int = 5435
    postgres18_db: str = "otrs"
    postgres18_user: str = "otrs"
    postgres18_password: str = ""

    rag_schema: str = "rag"
    conversa_schema: str = "conversa"
    embedding_model: str = "Qwen/Qwen3-Embedding-0.6B"
    embedding_dimension: int = 1024
    embedding_truncate_to: int | None = None
    embedding_batch: int = 64
    trecho_max_chars: int = 2000
    trecho_overlap_chars: int = 200
    processing_version: int = 1

    def conexao_otrs(self) -> dict[str, object]:
        """Argumentos de conexão psycopg para a cópia fixa do OTRS."""
        return {
            "host": self.postgres18_host,
            "port": self.postgres18_port,
            "dbname": self.postgres18_db,
            "user": self.postgres18_user,
            "password": self.postgres18_password,
        }
