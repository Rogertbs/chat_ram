from datetime import UTC, datetime

from chat_ram.conhecimento.consulta import FonteTickets, consultar_ticket
from chat_ram.conhecimento.dominio import (
    ArtigoBruto,
    StatusConsulta,
    TicketBruto,
)

DATA1 = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
DATA2 = datetime(2026, 1, 2, 9, 0, tzinfo=UTC)


def ticket(tn: str = "2026010100001", ticket_id: int = 1, fila: str = "Nivel 1") -> TicketBruto:
    return TicketBruto(tn=tn, ticket_id=ticket_id, titulo="Falha", fila=fila, situacao="aberto")


def artigo(
    article_id: int,
    *,
    ticket_id: int = 1,
    data: datetime = DATA1,
    visivel: bool = True,
    assunto: str = "Assunto",
    corpo: str = "Corpo",
) -> ArtigoBruto:
    return ArtigoBruto(
        article_id=article_id,
        ticket_id=ticket_id,
        data=data,
        visivel_cliente=visivel,
        assunto=assunto,
        corpo=corpo,
    )


class FonteFake:
    def __init__(self, tickets: list[tuple[TicketBruto, list[ArtigoBruto]]]) -> None:
        self._tickets = tickets

    def buscar_por_tn(self, tn: str) -> list[TicketBruto]:
        return [bruto for bruto, _ in self._tickets if bruto.tn == tn]

    def artigos_do_ticket(self, ticket_id: int) -> list[ArtigoBruto]:
        for bruto, artigos in self._tickets:
            if bruto.ticket_id == ticket_id:
                return list(artigos)
        return []


def test_ticket_encontrado_traz_artigos_cronologicos_com_fontes() -> None:
    fonte: FonteTickets = FonteFake(
        [
            (
                ticket(),
                [
                    artigo(10, data=DATA2, visivel=True, assunto="Resposta", corpo="segundo"),
                    artigo(11, data=DATA1, visivel=False, assunto="Nota", corpo="primeiro"),
                ],
            )
        ]
    )

    resultado = consultar_ticket(fonte, "2026010100001")

    assert resultado.status == StatusConsulta.ENCONTRADO
    assert resultado.ticket is not None
    assert [a.article_id for a in resultado.ticket.artigos] == [11, 10]
    assert resultado.ticket.artigos[0].visivel_cliente is False
    assert resultado.ticket.fila == "Nivel 1"
    assert resultado.ticket.situacao == "aberto"
    assert resultado.ticket.cobertura_parcial is False


def test_numero_inexistente_retorna_nao_encontrado() -> None:
    resultado = consultar_ticket(FonteFake([]), "9999999999999")

    assert resultado.status == StatusConsulta.NAO_ENCONTRADO
    assert resultado.ticket is None


def test_multiplos_correspondentes_retorna_ambiguo() -> None:
    fonte = FonteFake(
        [
            (ticket(ticket_id=1, fila="Nivel 1"), [artigo(1)]),
            (ticket(ticket_id=2, fila="Nivel 2"), [artigo(2, ticket_id=2)]),
        ]
    )

    resultado = consultar_ticket(fonte, "2026010100001")

    assert resultado.status == StatusConsulta.AMBIGUO
    assert resultado.ticket is None


def test_numero_com_espacos_e_normalizado() -> None:
    resultado = consultar_ticket(FonteFake([(ticket(), [artigo(1)])]), "  2026010100001  ")

    assert resultado.status == StatusConsulta.ENCONTRADO


def test_ticket_extenso_e_dividido_em_blocos_cronologicos() -> None:
    artigos = [artigo(i, data=DATA1, corpo="x" * 15) for i in range(1, 4)]

    resultado = consultar_ticket(FonteFake([(ticket(), artigos)]), "2026010100001", limite_bloco=20)

    assert resultado.ticket is not None
    assert resultado.ticket.cobertura_parcial is True
    assert len(resultado.ticket.blocos) == 3
    assert [b.indice_inicial for b in resultado.ticket.blocos] == [0, 1, 2]
    assert [len(b.artigos) for b in resultado.ticket.blocos] == [1, 1, 1]


def test_corpo_html_e_normalizado() -> None:
    fonte = FonteFake([(ticket(), [artigo(1, corpo="<p>Olá <b>mundo</b></p>")])])

    resultado = consultar_ticket(fonte, "2026010100001", limite_bloco=4000)

    assert resultado.ticket is not None
    assert resultado.ticket.artigos[0].corpo == "Olá mundo"
