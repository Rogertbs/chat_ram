"""Serialização do resultado da consulta para o contrato MCP."""

from typing import Any

from .dominio import ResultadoConsulta


def para_dicionario(resultado: ResultadoConsulta) -> dict[str, Any]:
    """Converte o resultado em um dicionário JSON-serializável."""
    if resultado.ticket is None:
        return {"status": resultado.status.value, "ticket": None}
    ticket = resultado.ticket
    return {
        "status": resultado.status.value,
        "ticket": {
            "tn": ticket.tn,
            "ticket_id": ticket.ticket_id,
            "titulo": ticket.titulo,
            "fila": ticket.fila,
            "situacao": ticket.situacao,
            "cobertura_parcial": ticket.cobertura_parcial,
            "artigos": [
                {
                    "article_id": artigo.article_id,
                    "data": artigo.data.isoformat(),
                    "visivel_cliente": artigo.visivel_cliente,
                    "assunto": artigo.assunto,
                    "corpo": artigo.corpo,
                }
                for artigo in ticket.artigos
            ],
            "blocos": [
                {
                    "indice_inicial": bloco.indice_inicial,
                    "caracteres": bloco.caracteres,
                    "article_ids": [artigo.article_id for artigo in bloco.artigos],
                }
                for bloco in ticket.blocos
            ],
        },
    }
