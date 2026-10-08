"""Servidor FastMCP que expõe o Conhecimento OTRS como ferramenta."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from .consulta import FonteTickets, consultar_ticket
from .dominio import StatusConsulta
from .serializacao import para_dicionario

_DESCRICAO = (
    "Consulta um ticket do OTRS pelo número público exato. Devolve o ticket com "
    "fila, situação e artigos em ordem cronológica, cada um com article_id, data e "
    "visibilidade (fonte conferível). Status: 'encontrado', 'nao_encontrado' (o "
    "número não existe — nunca invente), 'ambiguo' (mais de um ticket com o número) "
    "ou 'falha' (indisponibilidade técnica)."
)


def criar_servidor(fonte: FonteTickets, nome: str = "chat_ram-conhecimento") -> FastMCP:
    """Cria o servidor MCP com a ferramenta `consultar_ticket`."""
    servidor = FastMCP(nome)

    @servidor.tool(name="consultar_ticket", description=_DESCRICAO)
    def _consultar_ticket(numero: str) -> dict[str, Any]:
        try:
            return para_dicionario(consultar_ticket(fonte, numero))
        except Exception as exc:  # noqa: BLE001
            return {
                "status": StatusConsulta.FALHA.value,
                "ticket": None,
                "mensagem": f"falha técnica ao consultar: {exc}",
            }

    return servidor
