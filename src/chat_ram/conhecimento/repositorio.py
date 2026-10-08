"""Acesso somente-leitura à cópia fixa do OTRS no PostgreSQL 18."""

from typing import Any

import psycopg
from psycopg.rows import dict_row

from .dominio import ArtigoBruto, TicketBruto

_SQL_TICKET = """
SELECT t.id AS ticket_id,
       t.tn AS tn,
       COALESCE(t.title, '') AS titulo,
       q.name AS fila,
       COALESCE(ts.name, '') AS situacao
FROM ticket t
JOIN queue q ON q.id = t.queue_id
LEFT JOIN ticket_state ts ON ts.id = t.ticket_state_id
WHERE t.tn = %s
ORDER BY t.id
"""

_SQL_ARTIGOS = """
SELECT adm.article_id AS article_id,
       a.ticket_id AS ticket_id,
       a.create_time AS data,
       a.is_visible_for_customer AS visivel,
       COALESCE(adm.a_subject, '') AS assunto,
       COALESCE(adm.a_body, '') AS corpo
FROM article_data_mime adm
JOIN article a ON a.id = adm.article_id
WHERE a.ticket_id = %s
ORDER BY a.create_time ASC, adm.article_id ASC
"""


class PostgresTickets:
    """Implementa `FonteTickets` consultando as tabelas OTRS."""

    def __init__(self, conexao: psycopg.Connection[Any]) -> None:
        self._conexao = conexao

    def buscar_por_tn(self, tn: str) -> list[TicketBruto]:
        with self._conexao.cursor(row_factory=dict_row) as cursor:
            cursor.execute(_SQL_TICKET, (tn,))
            return [
                TicketBruto(
                    tn=str(linha["tn"]),
                    ticket_id=int(linha["ticket_id"]),
                    titulo=str(linha["titulo"]),
                    fila=str(linha["fila"]),
                    situacao=str(linha["situacao"]),
                )
                for linha in cursor.fetchall()
            ]

    def artigos_do_ticket(self, ticket_id: int) -> list[ArtigoBruto]:
        with self._conexao.cursor(row_factory=dict_row) as cursor:
            cursor.execute(_SQL_ARTIGOS, (ticket_id,))
            return [
                ArtigoBruto(
                    article_id=int(linha["article_id"]),
                    ticket_id=int(linha["ticket_id"]),
                    data=linha["data"],
                    visivel_cliente=bool(linha["visivel"]),
                    assunto=str(linha["assunto"]),
                    corpo=str(linha["corpo"]),
                )
                for linha in cursor.fetchall()
            ]
