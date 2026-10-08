"""Ponto de entrada ASGI (uvicorn chat_ram.main:app)."""

import psycopg

from .api import create_app
from .config import Settings
from .conhecimento.repositorio import PostgresTickets
from .conversa import Agente, Conversa, ferramenta_consultar_ticket
from .modelo import LiteLLMModel
from .persistencia.repositorio import PostgresConversas

settings = Settings()  # type: ignore[call-arg]
modelo = LiteLLMModel(settings.litellm_base_url, settings.litellm_api_key)
conexao = psycopg.connect(**settings.conexao_otrs())  # type: ignore[arg-type]
agente = Agente(modelo, [ferramenta_consultar_ticket(PostgresTickets(conexao))])
conversas = PostgresConversas(conexao, schema=settings.conversa_schema)
conversas.garantir_estrutura()
conversa = Conversa(agente, conversas, settings.model_alias)
app = create_app(modelo, settings, agente, conversa)
