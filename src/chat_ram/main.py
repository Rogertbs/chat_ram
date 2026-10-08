"""Ponto de entrada ASGI (uvicorn chat_ram.main:app)."""

import psycopg

from .api import create_app
from .config import Settings
from .conhecimento.repositorio import PostgresTickets
from .conversa import (
    Agente,
    Conversa,
    ferramenta_buscar_casos,
    ferramenta_consultar_ticket,
    ferramenta_resolver_filas,
)
from .modelo import LiteLLMModel
from .persistencia.repositorio import PostgresConversas
from .preparacao.embeddings import LiteLLMEmbeddings
from .preparacao.repositorio import PostgresTrechos

settings = Settings()  # type: ignore[call-arg]
modelo = LiteLLMModel(settings.litellm_base_url, settings.litellm_api_key)
conexao = psycopg.connect(**settings.conexao_otrs())  # type: ignore[arg-type]

tickets = PostgresTickets(conexao)
trechos = PostgresTrechos(conexao, schema=settings.rag_schema)
embeddings = LiteLLMEmbeddings(
    settings.litellm_base_url,
    settings.litellm_api_key,
    modelo=settings.embedding_model,
    dimensao=settings.embedding_dimension,
    lote=settings.embedding_batch,
    truncar_para=settings.embedding_truncate_to,
)
agente = Agente(
    modelo,
    [
        ferramenta_consultar_ticket(tickets),
        ferramenta_buscar_casos(trechos, embeddings),
        ferramenta_resolver_filas(tickets),
    ],
)
conversas = PostgresConversas(conexao, schema=settings.conversa_schema)
conversas.garantir_estrutura()
conversa = Conversa(agente, conversas, settings.model_alias)
app = create_app(modelo, settings, agente, conversa)
