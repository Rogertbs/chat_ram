"""Gera um banco mock do OTRS no PostgreSQL 18 a partir de dados fictícios.

Uso:
    python mock/gerar_banco.py
    python mock/gerar_banco.py --recriar --banco otrs_mock
    python -m mock.gerar_banco --dados mock/dados.json

Cria o banco (se faltar), o subconjunto de tabelas OTRS que a Preparação lê
e insere os chamados de `dados.json`. Nenhum dado real é tocado.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg

_AQUI = Path(__file__).resolve().parent
_DADOS_PADRAO = _AQUI / "dados.json"
_IDENTIFICADOR = re.compile(r"^[a-z_][a-z0-9_]*$")

_DDL = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_textsearch;
DROP TABLE IF EXISTS article_data_mime, article, ticket, queue CASCADE;

CREATE TABLE queue (
    id bigint PRIMARY KEY,
    name varchar(200) NOT NULL
);

CREATE TABLE ticket (
    id bigint PRIMARY KEY,
    tn varchar(50) NOT NULL,
    title varchar(255),
    queue_id bigint NOT NULL
);

CREATE TABLE article (
    id bigint PRIMARY KEY,
    ticket_id bigint NOT NULL,
    create_time timestamp with time zone NOT NULL,
    is_visible_for_customer smallint NOT NULL
);

CREATE TABLE article_data_mime (
    id bigint PRIMARY KEY,
    article_id bigint NOT NULL,
    a_subject text,
    a_body text
);
"""


def _valor_ambiente(nome: str, padrao: str | None = None) -> str | None:
    if nome in os.environ:
        return os.environ[nome]
    try:
        from dotenv import dotenv_values
    except ImportError:
        return padrao
    caminho = _AQUI.parent / ".env"
    if not caminho.exists():
        return padrao
    return dotenv_values(caminho).get(nome, padrao)


def _credenciais() -> dict[str, Any]:
    senha = _valor_ambiente("POSTGRES18_PASSWORD")
    if not senha:
        raise SystemExit("POSTGRES18_PASSWORD não definido no ambiente nem no .env")
    return {
        "host": _valor_ambiente("POSTGRES18_HOST", "127.0.0.1"),
        "port": int(_valor_ambiente("POSTGRES18_PORT", "5435") or "5435"),
        "user": _valor_ambiente("POSTGRES18_USER", "otrs"),
        "password": senha,
    }


def _criar_banco(credenciais: dict[str, Any], manutencao: str, banco: str, recriar: bool) -> None:
    if not _IDENTIFICADOR.match(banco):
        raise SystemExit(f"nome de banco inválido: {banco!r}")
    with (
        psycopg.connect(**credenciais, dbname=manutencao, autocommit=True) as conexao,
        conexao.cursor() as cursor,
    ):
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (banco,))
        existe = cursor.fetchone() is not None
        if existe and recriar:
            cursor.execute(f'DROP DATABASE IF EXISTS "{banco}" WITH (FORCE)')
            existe = False
        if not existe:
            cursor.execute(f'CREATE DATABASE "{banco}"')


def _inserir(conexao: psycopg.Connection[Any], dados: dict[str, Any]) -> tuple[int, int]:
    filas: list[str] = dados["filas"]
    id_fila = {nome: indice + 1 for indice, nome in enumerate(filas)}
    chamados: list[dict[str, Any]] = dados["chamados"]

    with conexao.cursor() as cursor:
        cursor.execute(_DDL)
        cursor.executemany(
            "INSERT INTO queue (id, name) VALUES (%s, %s)",
            [(id_fila[nome], nome) for nome in filas],
        )
        total_artigos = 0
        for ticket_id, chamado in enumerate(chamados, start=1):
            cursor.execute(
                "INSERT INTO ticket (id, tn, title, queue_id) VALUES (%s, %s, %s, %s)",
                (ticket_id, chamado["tn"], chamado["titulo"], id_fila[chamado["fila"]]),
            )
            for artigo in chamado["artigos"]:
                total_artigos += 1
                cursor.execute(
                    "INSERT INTO article (id, ticket_id, create_time, is_visible_for_customer) "
                    "VALUES (%s, %s, %s, %s)",
                    (
                        total_artigos,
                        ticket_id,
                        datetime.fromisoformat(artigo["data"]),
                        1 if artigo["visivel_cliente"] else 0,
                    ),
                )
                cursor.execute(
                    "INSERT INTO article_data_mime (id, article_id, a_subject, a_body) "
                    "VALUES (%s, %s, %s, %s)",
                    (total_artigos, total_artigos, artigo["assunto"], artigo["corpo"]),
                )
    conexao.commit()
    return len(chamados), total_artigos


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gera o banco mock do OTRS")
    parser.add_argument("--banco", default="otrs_mock", help="nome do banco mock")
    parser.add_argument("--dados", default=str(_DADOS_PADRAO), help="arquivo JSON dos chamados")
    parser.add_argument("--manutencao", default="postgres", help="banco usado para criar o mock")
    parser.add_argument("--recriar", action="store_true", help="apaga e recria o banco mock")
    args = parser.parse_args(argv)

    dados = json.loads(Path(args.dados).read_text(encoding="utf-8"))
    credenciais = _credenciais()

    _criar_banco(credenciais, args.manutencao, args.banco, args.recriar)
    with psycopg.connect(**credenciais, dbname=args.banco) as conexao:
        chamados, artigos = _inserir(conexao, dados)

    print(
        f"Banco '{args.banco}' pronto: {len(dados['filas'])} filas, "
        f"{chamados} chamados, {artigos} artigos."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
