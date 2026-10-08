"""Tipos do módulo de Conhecimento OTRS."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class StatusConsulta(StrEnum):
    """Desfecho de uma consulta por número de ticket."""

    ENCONTRADO = "encontrado"
    NAO_ENCONTRADO = "nao_encontrado"
    AMBIGUO = "ambiguo"
    FALHA = "falha"


@dataclass(frozen=True)
class TicketBruto:
    """Ticket lido do OTRS, antes de montar a consulta."""

    tn: str
    ticket_id: int
    titulo: str
    fila: str
    situacao: str


@dataclass(frozen=True)
class ArtigoBruto:
    """Artigo lido do OTRS, ainda com HTML."""

    article_id: int
    ticket_id: int
    data: datetime
    visivel_cliente: bool
    assunto: str
    corpo: str


@dataclass(frozen=True)
class ArtigoConsulta:
    """Artigo já normalizado, com a fonte conferível."""

    article_id: int
    data: datetime
    visivel_cliente: bool
    assunto: str
    corpo: str


@dataclass(frozen=True)
class Bloco:
    """Grupo cronológico de artigos dentro de um orçamento de caracteres."""

    indice_inicial: int
    artigos: tuple[ArtigoConsulta, ...]
    caracteres: int


@dataclass(frozen=True)
class TicketConsulta:
    """Ticket com artigos cronológicos e cobertura indicada."""

    tn: str
    ticket_id: int
    titulo: str
    fila: str
    situacao: str
    artigos: tuple[ArtigoConsulta, ...]
    blocos: tuple[Bloco, ...]
    cobertura_parcial: bool


@dataclass(frozen=True)
class ResultadoConsulta:
    """Resultado de `consultar_ticket`."""

    status: StatusConsulta
    ticket: TicketConsulta | None = None
