"""Executa o servidor MCP do Conhecimento OTRS.

Uso:
    python -m chat_ram.conhecimento
    python -m chat_ram.conhecimento --transporte streamable-http
"""

import argparse
from collections.abc import Sequence

import psycopg

from ..config import Settings
from .mcp import criar_servidor
from .repositorio import PostgresTickets


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Servidor MCP do Conhecimento OTRS")
    parser.add_argument(
        "--transporte",
        choices=["stdio", "streamable-http", "sse"],
        default="stdio",
        help="transporte do MCP",
    )
    args = parser.parse_args(argv)

    settings = Settings()  # type: ignore[call-arg]
    conexao = psycopg.connect(**settings.conexao_otrs())  # type: ignore[arg-type]
    try:
        servidor = criar_servidor(PostgresTickets(conexao))
        servidor.run(transport=args.transporte)
    finally:
        conexao.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
