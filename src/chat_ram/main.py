"""Ponto de entrada ASGI (uvicorn chat_ram.main:app)."""

import psycopg

from .api import create_app
from .config import Settings
from .conhecimento.repositorio import PostgresTickets
from .conversa import Agente, ferramenta_consultar_ticket
from .modelo import LiteLLMModel

settings = Settings()  # type: ignore[call-arg]
modelo = LiteLLMModel(settings.litellm_base_url, settings.litellm_api_key)
conexao = psycopg.connect(**settings.conexao_otrs())  # type: ignore[arg-type]
agente = Agente(modelo, [ferramenta_consultar_ticket(PostgresTickets(conexao))])
app = create_app(modelo, settings, agente)
