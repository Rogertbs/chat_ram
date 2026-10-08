"""Persistência da conversa: tabela `chat`, mensagens e estado por thread_id."""

from typing import Any, Protocol

import psycopg
from psycopg.rows import dict_row

from .dominio import EstadoConversa


class RepositorioConversas(Protocol):
    """Guarda o vínculo chat↔thread, as mensagens e o estado da conversa."""

    def resolver_thread(self, chat_id: str) -> str:
        """Devolve o thread_id do chat, criando o vínculo se faltar."""
        ...

    def carregar_mensagens(self, thread_id: str) -> list[dict[str, str]]:
        """Mensagens persistidas, em ordem."""
        ...

    def salvar_mensagem(self, thread_id: str, request_id: str, papel: str, conteudo: str) -> bool:
        """Grava uma mensagem; devolve False se já existia (retentativa)."""
        ...

    def carregar_resposta(
        self, thread_id: str, request_id: str, papel: str = "assistant"
    ) -> str | None:
        """Conteúdo já gravado de uma mensagem, para devolver em retentativa."""
        ...

    def carregar_estado(self, thread_id: str) -> EstadoConversa:
        """Estado persistido da conversa."""
        ...

    def salvar_estado(self, thread_id: str, estado: EstadoConversa) -> None:
        """Grava ou atualiza o estado da conversa."""
        ...


class PostgresConversas:
    """Implementação no PostgreSQL 18, em schema próprio (padrão `conversa`)."""

    def __init__(self, conexao: psycopg.Connection[Any], schema: str = "conversa") -> None:
        self._conexao = conexao
        self._schema = schema

    def garantir_estrutura(self) -> None:
        s = self._schema
        with self._conexao.cursor() as cursor:
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {s}")
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {s}.chat (
                    chat_id text PRIMARY KEY,
                    thread_id text NOT NULL UNIQUE,
                    titulo text,
                    criado_em timestamp with time zone NOT NULL DEFAULT now(),
                    atualizado_em timestamp with time zone NOT NULL DEFAULT now()
                )
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {s}.mensagem (
                    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    thread_id text NOT NULL,
                    request_id text NOT NULL,
                    papel text NOT NULL,
                    conteudo text NOT NULL,
                    criado_em timestamp with time zone NOT NULL DEFAULT now(),
                    UNIQUE (thread_id, request_id, papel)
                )
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {s}.estado (
                    thread_id text PRIMARY KEY,
                    fila_selecionada text,
                    ticket_em_foco text,
                    esclarecimentos jsonb NOT NULL DEFAULT '[]'::jsonb,
                    atualizado_em timestamp with time zone NOT NULL DEFAULT now()
                )
                """
            )
        self._conexao.commit()

    def resolver_thread(self, chat_id: str) -> str:
        s = self._schema
        with self._conexao.cursor() as cursor:
            cursor.execute(f"SELECT thread_id FROM {s}.chat WHERE chat_id = %s", (chat_id,))
            linha = cursor.fetchone()
            if linha is not None:
                return str(linha[0])
            cursor.execute(
                f"""
                INSERT INTO {s}.chat (chat_id, thread_id) VALUES (%s, %s)
                ON CONFLICT (chat_id) DO UPDATE SET atualizado_em = now()
                RETURNING thread_id
                """,
                (chat_id, chat_id),
            )
            linha = cursor.fetchone()
            if linha is None:
                raise RuntimeError("não foi possível registrar a conversa")
            thread_id = str(linha[0])
        self._conexao.commit()
        return thread_id

    def carregar_mensagens(self, thread_id: str) -> list[dict[str, str]]:
        with self._conexao.cursor() as cursor:
            cursor.execute(
                f"SELECT papel, conteudo FROM {self._schema}.mensagem "
                "WHERE thread_id = %s ORDER BY id",
                (thread_id,),
            )
            return [
                {"role": str(linha[0]), "content": str(linha[1])} for linha in cursor.fetchall()
            ]

    def salvar_mensagem(self, thread_id: str, request_id: str, papel: str, conteudo: str) -> bool:
        with self._conexao.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {self._schema}.mensagem (thread_id, request_id, papel, conteudo)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (thread_id, request_id, papel) DO NOTHING
                """,
                (thread_id, request_id, papel, conteudo),
            )
            inserida = cursor.rowcount > 0
        self._conexao.commit()
        return inserida

    def carregar_resposta(
        self, thread_id: str, request_id: str, papel: str = "assistant"
    ) -> str | None:
        with self._conexao.cursor() as cursor:
            cursor.execute(
                f"SELECT conteudo FROM {self._schema}.mensagem "
                "WHERE thread_id = %s AND request_id = %s AND papel = %s",
                (thread_id, request_id, papel),
            )
            linha = cursor.fetchone()
        return None if linha is None else str(linha[0])

    def carregar_estado(self, thread_id: str) -> EstadoConversa:
        with self._conexao.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                f"SELECT fila_selecionada, ticket_em_foco, esclarecimentos "
                f"FROM {self._schema}.estado WHERE thread_id = %s",
                (thread_id,),
            )
            linha = cursor.fetchone()
        if linha is None:
            return EstadoConversa()
        return EstadoConversa(
            fila_selecionada=linha["fila_selecionada"],
            ticket_em_foco=linha["ticket_em_foco"],
            esclarecimentos=list(linha["esclarecimentos"] or []),
        )

    def salvar_estado(self, thread_id: str, estado: EstadoConversa) -> None:
        with self._conexao.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {self._schema}.estado
                    (thread_id, fila_selecionada, ticket_em_foco, esclarecimentos, atualizado_em)
                VALUES (%s, %s, %s, %s::jsonb, now())
                ON CONFLICT (thread_id) DO UPDATE SET
                    fila_selecionada = EXCLUDED.fila_selecionada,
                    ticket_em_foco = EXCLUDED.ticket_em_foco,
                    esclarecimentos = EXCLUDED.esclarecimentos,
                    atualizado_em = now()
                """,
                (
                    thread_id,
                    estado.fila_selecionada,
                    estado.ticket_em_foco,
                    _json(estado.esclarecimentos),
                ),
            )
        self._conexao.commit()


def _json(valores: list[str]) -> str:
    import json

    return json.dumps(valores, ensure_ascii=False)
