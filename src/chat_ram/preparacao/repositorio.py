"""Persistência dos trechos e índices de busca."""

import re
from typing import Any, Protocol

import psycopg
from psycopg.rows import dict_row

from .dominio import ConfiguracaoPreparacao, ResultadoBusca, Trecho

_IDENTIFICADOR = re.compile(r"^[a-z_][a-z0-9_]*$")

_COLUNAS = "tn, ticket_id, article_id, fila, data, visivel_cliente, posicao, content"


class RepositorioPreparacao(Protocol):
    """Contrato de escrita usado pela Preparação do histórico."""

    def garantir_estrutura(self, config: ConfiguracaoPreparacao) -> None:
        """Cria schema, tabela de trechos e índices, se faltarem."""
        ...

    def registrar_modelo(self, config: ConfiguracaoPreparacao) -> None:
        """Fixa o modelo ativo; recusa modelos/dimensões incompatíveis."""
        ...

    def artigos_processados(self, versao: int, modelo: str) -> set[int]:
        """IDs de artigos já gravados na versão/modelo, para retomada."""
        ...

    def salvar(self, trechos: list[Trecho]) -> None:
        """Substitui os trechos dos artigos informados, sem duplicar nem deixar órfãos."""
        ...

    def cobertura_por_fila(self) -> dict[str, int]:
        """Quantidade de trechos por fila."""
        ...


class RepositorioBusca(Protocol):
    """Contrato de leitura usado pela busca de casos semelhantes."""

    def buscar_lexical(
        self, consulta: str, limite: int = 50, filas: list[str] | None = None
    ) -> list[ResultadoBusca]:
        """Busca BM25 sobre o conteúdo, opcionalmente restrita a filas."""
        ...

    def buscar_vetorial(
        self, embedding: list[float], limite: int = 50, filas: list[str] | None = None
    ) -> list[ResultadoBusca]:
        """Busca por proximidade de cosseno, opcionalmente restrita a filas."""
        ...

    def similaridades(
        self, embedding: list[float], chaves: list[tuple[str, int, int]]
    ) -> dict[tuple[str, int, int], float]:
        """Similaridade de cosseno de cada trecho (tn, article_id, posicao)."""
        ...


class RepositorioTrechos(RepositorioPreparacao, RepositorioBusca, Protocol):
    """Contrato completo da tabela de trechos: escrita e busca."""


class PostgresTrechos:
    """Tabela derivada no PostgreSQL 18, com índices BM25 e HNSW.

    A coluna vetorial tem dimensão fixa (ADR 0001); a tabela de configuração
    registra o modelo ativo e recusa misturar vetores de modelos diferentes.
    """

    def __init__(self, conexao: psycopg.Connection[Any], schema: str = "rag") -> None:
        if not _IDENTIFICADOR.match(schema):
            raise ValueError(f"schema inválido: {schema!r}")
        self._conexao = conexao
        self._schema = schema

    def garantir_estrutura(self, config: ConfiguracaoPreparacao) -> None:
        s = self._schema
        with self._conexao.cursor() as cursor:
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {s}")
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {s}.trechos (
                    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    tn text NOT NULL,
                    ticket_id bigint NOT NULL,
                    article_id bigint NOT NULL,
                    fila text NOT NULL,
                    data timestamp with time zone NOT NULL,
                    visivel_cliente boolean NOT NULL,
                    posicao integer NOT NULL,
                    versao integer NOT NULL,
                    modelo_embeddings text NOT NULL,
                    dimensao integer NOT NULL,
                    content text NOT NULL,
                    embedding vector({int(config.dimensao)}) NOT NULL,
                    atualizado_em timestamp with time zone NOT NULL DEFAULT now(),
                    UNIQUE (article_id, posicao, versao)
                )
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {s}.config (
                    id integer PRIMARY KEY CHECK (id = 1),
                    modelo_embeddings text NOT NULL,
                    dimensao integer NOT NULL,
                    atualizado_em timestamp with time zone NOT NULL DEFAULT now()
                )
                """
            )
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS trechos_bm25 ON {s}.trechos "
                "USING bm25(content) WITH (text_config='portuguese')"
            )
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS trechos_vector ON {s}.trechos "
                "USING hnsw (embedding vector_cosine_ops)"
            )
            cursor.execute(f"CREATE INDEX IF NOT EXISTS trechos_fila ON {s}.trechos (fila)")
        self._conexao.commit()

    def registrar_modelo(self, config: ConfiguracaoPreparacao) -> None:
        s = self._schema
        with self._conexao.cursor(row_factory=dict_row) as cursor:
            cursor.execute(f"SELECT modelo_embeddings, dimensao FROM {s}.config WHERE id = 1")
            linha = cursor.fetchone()
            if linha is None:
                cursor.execute(
                    f"INSERT INTO {s}.config (id, modelo_embeddings, dimensao) VALUES (1, %s, %s)",
                    (config.modelo_embeddings, config.dimensao),
                )
            elif (
                linha["modelo_embeddings"] != config.modelo_embeddings
                or linha["dimensao"] != config.dimensao
            ):
                raise ValueError(
                    "modelo/dimensão incompatíveis com os vetores já gravados: "
                    f"tabela usa {linha['modelo_embeddings']!r} ({linha['dimensao']}), "
                    f"execução pede {config.modelo_embeddings!r} ({config.dimensao})"
                )
        self._conexao.commit()

    def artigos_processados(self, versao: int, modelo: str) -> set[int]:
        with self._conexao.cursor() as cursor:
            cursor.execute(
                f"SELECT DISTINCT article_id FROM {self._schema}.trechos "
                "WHERE versao = %s AND modelo_embeddings = %s",
                (versao, modelo),
            )
            return {int(linha[0]) for linha in cursor.fetchall()}

    def salvar(self, trechos: list[Trecho]) -> None:
        if not trechos:
            return
        parametros = [
            (
                trecho.tn,
                trecho.ticket_id,
                trecho.article_id,
                trecho.fila,
                trecho.data,
                trecho.visivel_cliente,
                trecho.posicao,
                trecho.versao,
                trecho.modelo_embeddings,
                trecho.dimensao,
                trecho.content,
                _vetor(trecho.embedding),
            )
            for trecho in trechos
        ]
        artigos = sorted({(trecho.article_id, trecho.versao) for trecho in trechos})
        with self._conexao.cursor() as cursor:
            for article_id, versao in artigos:
                cursor.execute(
                    f"DELETE FROM {self._schema}.trechos WHERE article_id = %s AND versao = %s",
                    (article_id, versao),
                )
            cursor.executemany(
                f"""
                INSERT INTO {self._schema}.trechos
                    (tn, ticket_id, article_id, fila, data, visivel_cliente, posicao,
                     versao, modelo_embeddings, dimensao, content, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
                ON CONFLICT (article_id, posicao, versao) DO UPDATE SET
                    tn = EXCLUDED.tn,
                    ticket_id = EXCLUDED.ticket_id,
                    fila = EXCLUDED.fila,
                    data = EXCLUDED.data,
                    visivel_cliente = EXCLUDED.visivel_cliente,
                    modelo_embeddings = EXCLUDED.modelo_embeddings,
                    dimensao = EXCLUDED.dimensao,
                    content = EXCLUDED.content,
                    embedding = EXCLUDED.embedding,
                    atualizado_em = now()
                """,
                parametros,
            )
        self._conexao.commit()

    def cobertura_por_fila(self) -> dict[str, int]:
        with self._conexao.cursor() as cursor:
            cursor.execute(
                f"SELECT fila, count(*) FROM {self._schema}.trechos GROUP BY fila ORDER BY fila"
            )
            return {str(linha[0]): int(linha[1]) for linha in cursor.fetchall()}

    def buscar_lexical(
        self, consulta: str, limite: int = 50, filas: list[str] | None = None
    ) -> list[ResultadoBusca]:
        filtro, parametros = _filtro_filas(filas)
        sql = f"""
            SELECT {_COLUNAS}, content <@> to_bm25query(%s, '{self._schema}.trechos_bm25') AS score
            FROM {self._schema}.trechos
            {filtro}
            ORDER BY score ASC, tn ASC, article_id ASC, posicao ASC
            LIMIT %s
        """
        with self._conexao.cursor(row_factory=dict_row) as cursor:
            cursor.execute(sql, [consulta, *parametros, limite])
            return [_resultado(linha) for linha in cursor.fetchall()]

    def buscar_vetorial(
        self, embedding: list[float], limite: int = 50, filas: list[str] | None = None
    ) -> list[ResultadoBusca]:
        filtro, parametros = _filtro_filas(filas)
        sql = f"""
            SELECT {_COLUNAS}, embedding <=> %s::vector AS score
            FROM {self._schema}.trechos
            {filtro}
            ORDER BY score ASC, tn ASC, article_id ASC, posicao ASC
            LIMIT %s
        """
        with self._conexao.cursor(row_factory=dict_row) as cursor:
            cursor.execute(sql, [_vetor(embedding), *parametros, limite])
            return [_resultado(linha) for linha in cursor.fetchall()]

    def similaridades(
        self, embedding: list[float], chaves: list[tuple[str, int, int]]
    ) -> dict[tuple[str, int, int], float]:
        if not chaves:
            return {}
        valores = ", ".join(["(%s, %s, %s)"] * len(chaves))
        parametros: list[Any] = [_vetor(embedding)]
        for tn, article_id, posicao in chaves:
            parametros.extend([tn, article_id, posicao])
        sql = f"""
            SELECT tn, article_id, posicao, 1 - (embedding <=> %s::vector) AS similaridade
            FROM {self._schema}.trechos
            WHERE (tn, article_id, posicao) IN ({valores})
        """
        with self._conexao.cursor(row_factory=dict_row) as cursor:
            cursor.execute(sql, parametros)
            return {
                (str(linha["tn"]), int(linha["article_id"]), int(linha["posicao"])): float(
                    linha["similaridade"]
                )
                for linha in cursor.fetchall()
            }


def _filtro_filas(filas: list[str] | None) -> tuple[str, list[Any]]:
    if not filas:
        return "", []
    return "WHERE fila = ANY(%s)", [list(filas)]


def _resultado(linha: dict[str, Any]) -> ResultadoBusca:
    return ResultadoBusca(
        tn=str(linha["tn"]),
        ticket_id=int(linha["ticket_id"]),
        article_id=int(linha["article_id"]),
        fila=str(linha["fila"]),
        data=linha["data"],
        visivel_cliente=bool(linha["visivel_cliente"]),
        posicao=int(linha["posicao"]),
        content=str(linha["content"]),
        score=float(linha["score"]),
    )


def _vetor(embedding: list[float] | tuple[float, ...]) -> str:
    return "[" + ",".join(str(float(valor)) for valor in embedding) + "]"
