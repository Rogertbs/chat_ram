"""Leitura da cópia fixa do OTRS."""

from collections.abc import Iterator
from typing import Any, Protocol

import psycopg
from psycopg.rows import dict_row

from .dominio import Artigo

_SQL_ARTIGOS = """
SELECT t.tn AS tn,
       t.id AS ticket_id,
       adm.article_id AS article_id,
       q.name AS fila,
       a.create_time AS data,
       a.is_visible_for_customer AS visivel,
       COALESCE(adm.a_subject, '') AS assunto,
       COALESCE(adm.a_body, '') AS corpo
FROM article_data_mime adm
JOIN article a ON a.id = adm.article_id
JOIN ticket t ON t.id = a.ticket_id
JOIN queue q ON q.id = t.queue_id
ORDER BY adm.article_id
"""


class FonteHistorico(Protocol):
    """Fornece os artigos do histórico, em ordem determinística."""

    def artigos(self, limite: int | None = None) -> Iterator[Artigo]:
        """Percorre os artigos com metadados do ticket e da fila."""
        ...


class PostgresHistorico:
    """Lê artigo_data_mime ligado a article, ticket e queue na cópia fixa."""

    def __init__(self, conexao: psycopg.Connection[Any]) -> None:
        self._conexao = conexao

    def artigos(self, limite: int | None = None) -> Iterator[Artigo]:
        sql = _SQL_ARTIGOS
        parametros: tuple[int, ...] = ()
        if limite is not None:
            sql = f"{sql} LIMIT %s"
            parametros = (limite,)
        with self._conexao.cursor(name="artigos_otrs", row_factory=dict_row) as cursor:
            cursor.itersize = 1000
            cursor.execute(sql, parametros)
            for linha in cursor:
                yield Artigo(
                    tn=str(linha["tn"]),
                    ticket_id=int(linha["ticket_id"]),
                    article_id=int(linha["article_id"]),
                    fila=str(linha["fila"]),
                    data=linha["data"],
                    visivel_cliente=bool(linha["visivel"]),
                    assunto=str(linha["assunto"]),
                    corpo=str(linha["corpo"]),
                )
