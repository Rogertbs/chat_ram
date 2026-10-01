"""Configuração da aplicação, lida do ambiente / .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Conexão ao proxy LiteLLM e alias do modelo."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    litellm_base_url: str
    litellm_api_key: str = "sk-local"
    model_alias: str
