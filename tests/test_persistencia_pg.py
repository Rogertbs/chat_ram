"""Integração da persistência da conversa com o PostgreSQL 18."""

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import psycopg
import pytest

from chat_ram.persistencia.dominio import EstadoConversa
from chat_ram.persistencia.repositorio import PostgresConversas


@pytest.fixture
def conversas(conexao_pg18: psycopg.Connection[Any]) -> Iterator[PostgresConversas]:
    schema = f"conversa_teste_{uuid4().hex[:8]}"
    repo = PostgresConversas(conexao_pg18, schema=schema)
    repo.garantir_estrutura()
    try:
        yield repo
    finally:
        conexao_pg18.rollback()
        with conexao_pg18.cursor() as cursor:
            cursor.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        conexao_pg18.commit()


def test_vinculo_chat_thread_e_estavel(conversas: PostgresConversas) -> None:
    thread = conversas.resolver_thread("chat-1")

    assert conversas.resolver_thread("chat-1") == thread
    assert conversas.resolver_thread("chat-2") != thread


def test_mensagens_sao_idempotentes_por_requisicao(conversas: PostgresConversas) -> None:
    thread = conversas.resolver_thread("chat-1")

    conversas.salvar_mensagem(thread, "req-1", "user", "oi")
    conversas.salvar_mensagem(thread, "req-1", "assistant", "olá")
    conversas.salvar_mensagem(thread, "req-1", "user", "oi")

    assert conversas.carregar_mensagens(thread) == [
        {"role": "user", "content": "oi"},
        {"role": "assistant", "content": "olá"},
    ]


def test_conversas_diferentes_nao_compartilham_mensagens(
    conversas: PostgresConversas,
) -> None:
    a = conversas.resolver_thread("chat-a")
    b = conversas.resolver_thread("chat-b")

    conversas.salvar_mensagem(a, "ra", "user", "assunto A")
    conversas.salvar_mensagem(b, "rb", "user", "assunto B")

    assert conversas.carregar_mensagens(a) == [{"role": "user", "content": "assunto A"}]
    assert conversas.carregar_mensagens(b) == [{"role": "user", "content": "assunto B"}]


def test_estado_da_conversa_persiste(conversas: PostgresConversas) -> None:
    thread = conversas.resolver_thread("chat-1")

    conversas.salvar_estado(
        thread,
        EstadoConversa(
            fila_selecionada="Infraestrutura", ticket_em_foco="123", esclarecimentos=["a"]
        ),
    )

    estado = conversas.carregar_estado(thread)
    assert estado.fila_selecionada == "Infraestrutura"
    assert estado.ticket_em_foco == "123"
    assert estado.esclarecimentos == ["a"]
    assert conversas.carregar_estado("inexistente") == EstadoConversa()
