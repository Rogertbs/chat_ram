"""Servidor FastMCP que expõe o Conhecimento OTRS como ferramentas."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from .busca import Embeddings, FonteBusca, FonteFilas, buscar_casos, resolver_filas
from .consulta import FonteTickets, consultar_ticket
from .dominio import StatusConsulta
from .serializacao import casos_para_dicionario, para_dicionario

_DESCRICAO_CONSULTAR = (
    "Consulta um ticket do OTRS pelo número público exato. Devolve o ticket com "
    "fila, situação e artigos em ordem cronológica, cada um com article_id, data e "
    "visibilidade (fonte conferível). Status: 'encontrado', 'nao_encontrado' (o "
    "número não existe — nunca invente), 'ambiguo' (mais de um ticket com o número) "
    "ou 'falha' (indisponibilidade técnica)."
)
_DESCRICAO_BUSCAR = (
    "Busca casos semelhantes no histórico pela descrição do problema (BM25 + vetor, "
    "fundidos por RRF). Devolve os melhores trechos com fontes. Se 'alcance_suficiente' "
    "for falso, declare o alcance da busca e não invente."
)
_DESCRICAO_FILAS = (
    "Resolve o nome de uma fila informado pelo usuário. Devolve os candidatos; se "
    "'ambiguo' for verdadeiro, peça esclarecimento antes de buscar."
)


def criar_servidor(
    fonte: FonteTickets,
    *,
    busca: FonteBusca | None = None,
    embeddings: Embeddings | None = None,
    filas: FonteFilas | None = None,
    nome: str = "chat_ram-conhecimento",
) -> FastMCP:
    """Cria o servidor MCP com as ferramentas de Conhecimento OTRS disponíveis."""
    servidor = FastMCP(nome)

    @servidor.tool(name="consultar_ticket", description=_DESCRICAO_CONSULTAR)
    def _consultar_ticket(numero: str) -> dict[str, Any]:
        try:
            return para_dicionario(consultar_ticket(fonte, numero))
        except Exception as exc:  # noqa: BLE001
            return {
                "status": StatusConsulta.FALHA.value,
                "ticket": None,
                "mensagem": f"falha técnica ao consultar: {exc}",
            }

    if busca is not None and embeddings is not None:

        @servidor.tool(name="buscar_casos", description=_DESCRICAO_BUSCAR)
        def _buscar_casos(pergunta: str, filas_busca: list[str] | None = None) -> dict[str, Any]:
            try:
                return casos_para_dicionario(buscar_casos(busca, embeddings, pergunta, filas_busca))
            except Exception as exc:  # noqa: BLE001
                return {"status": "falha", "casos": [], "mensagem": f"falha técnica: {exc}"}

    if filas is not None:

        @servidor.tool(name="resolver_filas", description=_DESCRICAO_FILAS)
        def _resolver_filas(texto: str) -> dict[str, Any]:
            resultado = resolver_filas(filas.listar_filas(), texto)
            return {"candidatos": list(resultado.candidatos), "ambiguo": resultado.ambiguo}

    return servidor
