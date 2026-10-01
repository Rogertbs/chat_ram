"""Ponto de entrada ASGI (uvicorn chat_ram.main:app)."""

from .api import create_app
from .config import Settings
from .modelo import LiteLLMModel

settings = Settings()  # type: ignore[call-arg]
modelo = LiteLLMModel(settings.litellm_base_url, settings.litellm_api_key)
app = create_app(modelo, settings)
