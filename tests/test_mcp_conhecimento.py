from datetime import UTC, datetime
from typing import Any, cast

from chat_ram.conhecimento.dominio import ArtigoBruto, TicketBruto
from chat_ram.conhecimento.mcp import criar_servidor

DATA = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)


class FonteFake:
    def __init__(self, falhar: bool = False) -> None:
        self._falhar = falhar

    def buscar_por_tn(self, tn: str) -> list[TicketBruto]:
        if self._falhar:
            raise RuntimeError("banco fora do ar")
        if tn != "123":
            return []
        return [TicketBruto(tn="123", ticket_id=1, titulo="T", fila="Nivel 1", situacao="aberto")]

    def artigos_do_ticket(self, ticket_id: int) -> list[ArtigoBruto]:
        return [
            ArtigoBruto(
                article_id=5,
                ticket_id=ticket_id,
                data=DATA,
                visivel_cliente=True,
                assunto="Assunto",
                corpo="Corpo",
            )
        ]


async def _chamar(servidor: Any, numero: str) -> dict[str, Any]:
    resultado = await servidor.call_tool("consultar_ticket", {"numero": numero})
    if isinstance(resultado, tuple):
        return cast("dict[str, Any]", resultado[1])
    return cast("dict[str, Any]", resultado)


async def test_ferramenta_consultar_ticket_e_listada() -> None:
    servidor = criar_servidor(FonteFake())

    ferramentas = await servidor.list_tools()
    ferramenta = next(f for f in ferramentas if f.name == "consultar_ticket")

    assert "numero" in ferramenta.inputSchema["properties"]


async def test_ferramenta_retorna_o_ticket_com_fontes() -> None:
    servidor = criar_servidor(FonteFake())

    resultado = await _chamar(servidor, "123")

    assert resultado["status"] == "encontrado"
    assert resultado["ticket"]["fila"] == "Nivel 1"
    assert resultado["ticket"]["artigos"][0]["article_id"] == 5


async def test_ferramenta_reporta_nao_encontrado() -> None:
    servidor = criar_servidor(FonteFake())

    resultado = await _chamar(servidor, "999")

    assert resultado["status"] == "nao_encontrado"
    assert resultado["ticket"] is None


async def test_ferramenta_reporta_falha_tecnica_sem_quebrar() -> None:
    servidor = criar_servidor(FonteFake(falhar=True))

    resultado = await _chamar(servidor, "123")

    assert resultado["status"] == "falha"
    assert resultado["ticket"] is None
    assert "falha técnica" in resultado["mensagem"]
