"""Módulo de Conhecimento OTRS: consulta exata por número de ticket."""

from typing import Protocol

from ..preparacao.texto import normalizar_html
from .dominio import (
    ArtigoBruto,
    ArtigoConsulta,
    Bloco,
    ResultadoConsulta,
    StatusConsulta,
    TicketBruto,
    TicketConsulta,
)

LIMITE_BLOCO_PADRAO = 4000


class FonteTickets(Protocol):
    """Acesso somente-leitura à cópia fixa do OTRS."""

    def buscar_por_tn(self, tn: str) -> list[TicketBruto]:
        """Tickets cujo número público é exatamente `tn`."""
        ...

    def artigos_do_ticket(self, ticket_id: int) -> list[ArtigoBruto]:
        """Artigos do ticket, em qualquer ordem."""
        ...


def consultar_ticket(
    fonte: FonteTickets,
    numero: str,
    *,
    limite_bloco: int = LIMITE_BLOCO_PADRAO,
) -> ResultadoConsulta:
    """Consulta um ticket pelo número público exato e monta o resumo estrutural.

    Nunca escolhe por similaridade. Distingue não encontrado de ambíguo
    (mais de um ticket com o mesmo número).
    """
    tn = numero.strip()
    if not tn:
        return ResultadoConsulta(StatusConsulta.NAO_ENCONTRADO)

    candidatos = fonte.buscar_por_tn(tn)
    if not candidatos:
        return ResultadoConsulta(StatusConsulta.NAO_ENCONTRADO)
    if len(candidatos) > 1:
        return ResultadoConsulta(StatusConsulta.AMBIGUO)

    bruto = candidatos[0]
    artigos = sorted(
        fonte.artigos_do_ticket(bruto.ticket_id),
        key=lambda artigo: (artigo.data, artigo.article_id),
    )
    consulta = tuple(_para_consulta(artigo) for artigo in artigos)
    blocos = montar_blocos(consulta, limite_bloco)
    return ResultadoConsulta(
        StatusConsulta.ENCONTRADO,
        TicketConsulta(
            tn=bruto.tn,
            ticket_id=bruto.ticket_id,
            titulo=bruto.titulo,
            fila=bruto.fila,
            situacao=bruto.situacao,
            artigos=consulta,
            blocos=blocos,
            cobertura_parcial=len(blocos) > 1,
        ),
    )


def montar_blocos(
    artigos: tuple[ArtigoConsulta, ...] | list[ArtigoConsulta], limite: int
) -> tuple[Bloco, ...]:
    """Agrupa artigos consecutivos em blocos que cabem no orçamento de caracteres."""
    blocos: list[Bloco] = []
    atual: list[ArtigoConsulta] = []
    caracteres = 0
    inicio = 0
    for indice, artigo in enumerate(artigos):
        peso = len(artigo.assunto) + len(artigo.corpo)
        if atual and caracteres + peso > limite:
            blocos.append(Bloco(inicio, tuple(atual), caracteres))
            atual = []
            caracteres = 0
            inicio = indice
        if not atual:
            inicio = indice
        atual.append(artigo)
        caracteres += peso
    if atual:
        blocos.append(Bloco(inicio, tuple(atual), caracteres))
    return tuple(blocos)


def _para_consulta(artigo: ArtigoBruto) -> ArtigoConsulta:
    return ArtigoConsulta(
        article_id=artigo.article_id,
        data=artigo.data,
        visivel_cliente=artigo.visivel_cliente,
        assunto=normalizar_html(artigo.assunto),
        corpo=normalizar_html(artigo.corpo),
    )
