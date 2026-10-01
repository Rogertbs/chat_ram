"""Preparação do histórico em lote: ``python -m chat_ram.preparacao``."""

import argparse
import json
from dataclasses import asdict
from typing import Any

import psycopg

from ..config import Settings
from .dominio import ConfiguracaoPreparacao
from .embeddings import LiteLLMEmbeddings
from .historico import PostgresHistorico
from .preparador import preparar
from .repositorio import PostgresTrechos


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preparação do histórico do OTRS")
    parser.add_argument(
        "--limite", type=int, default=None, help="máximo de artigos a processar nesta execução"
    )
    parser.add_argument(
        "--nao-retomar", action="store_true", help="reprocessa inclusive artigos já gravados"
    )
    args = parser.parse_args(argv)

    settings = Settings()  # type: ignore[call-arg]
    config = ConfiguracaoPreparacao(
        modelo_embeddings=settings.embedding_model,
        dimensao=settings.embedding_dimension,
        versao=settings.processing_version,
        tamanho_max=settings.trecho_max_chars,
        sobreposicao=settings.trecho_overlap_chars,
        lote_embeddings=settings.embedding_batch,
        retomar=not args.nao_retomar,
    )
    conexao_leitura = _conectar(settings)
    conexao_escrita = _conectar(settings)
    try:
        relatorio = preparar(
            PostgresHistorico(conexao_leitura),
            LiteLLMEmbeddings(
                settings.litellm_base_url,
                settings.litellm_api_key,
                modelo=settings.embedding_model,
                dimensao=settings.embedding_dimension,
                lote=settings.embedding_batch,
            ),
            PostgresTrechos(conexao_escrita, schema=settings.rag_schema),
            config,
            limite=args.limite,
        )
    finally:
        conexao_leitura.close()
        conexao_escrita.close()

    print(json.dumps(asdict(relatorio), ensure_ascii=False, indent=2))
    return 0


def _conectar(settings: Settings) -> psycopg.Connection[Any]:
    return psycopg.connect(
        host=settings.postgres18_host,
        port=settings.postgres18_port,
        dbname=settings.postgres18_db,
        user=settings.postgres18_user,
        password=settings.postgres18_password,
    )


if __name__ == "__main__":
    raise SystemExit(main())
