"""Fixtures compartilhadas. A conexão ao PostgreSQL 18 é opcional."""

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest


def _valor_ambiente(nome: str, padrao: str | None = None) -> str | None:
    if nome in os.environ:
        return os.environ[nome]
    try:
        from dotenv import dotenv_values
    except ImportError:
        return padrao
    caminho = Path(__file__).resolve().parent.parent / ".env"
    if not caminho.exists():
        return padrao
    return dotenv_values(caminho).get(nome, padrao)


@pytest.fixture
def conexao_pg18() -> Iterator[psycopg.Connection[Any]]:
    """Conexão à cópia fixa no PostgreSQL 18, ou pula o teste."""
    senha = _valor_ambiente("POSTGRES18_PASSWORD")
    if not senha:
        pytest.skip("POSTGRES18_PASSWORD não definido; integração com PostgreSQL 18 ignorada")
    try:
        conexao = psycopg.connect(
            host=_valor_ambiente("POSTGRES18_HOST", "127.0.0.1"),
            port=int(_valor_ambiente("POSTGRES18_PORT", "5435") or "5435"),
            dbname=_valor_ambiente("POSTGRES18_DB", "otrs"),
            user=_valor_ambiente("POSTGRES18_USER", "otrs"),
            password=senha,
        )
    except psycopg.OperationalError as exc:
        pytest.skip(f"PostgreSQL 18 indisponível: {exc}")
    yield conexao
    conexao.close()
