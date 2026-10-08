from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from chat_ram.conhecimento.dominio import ArtigoBruto, TicketBruto
from chat_ram.conversa import (
    Agente,
    ferramenta_buscar_casos,
    ferramenta_consultar_ticket,
    ferramenta_resolver_filas,
)
from chat_ram.modelo import EventoFerramentas, EventoModelo, EventoTexto
from chat_ram.preparacao.dominio import ResultadoBusca

DATA = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)


class FonteFake:
    def __init__(self, vazio: bool = False) -> None:
        self._vazio = vazio
        self.consultados: list[str] = []

    def buscar_por_tn(self, tn: str) -> list[TicketBruto]:
        self.consultados.append(tn)
        if self._vazio:
            return []
        return [TicketBruto(tn=tn, ticket_id=1, titulo="T", fila="Nivel 1", situacao="aberto")]

    def artigos_do_ticket(self, ticket_id: int) -> list[ArtigoBruto]:
        return [ArtigoBruto(5, ticket_id, DATA, True, "Assunto", "Corpo")]


class ModeloFake:
    def __init__(self, roteiro: list[list[EventoModelo]]) -> None:
        self._roteiro = list(roteiro)
        self.chamadas: list[dict[str, Any]] = []

    async def stream_eventos(
        self,
        mensagens: list[dict[str, Any]],
        ferramentas: list[dict[str, Any]],
        modelo: str,
    ) -> AsyncIterator[EventoModelo]:
        self.chamadas.append({"mensagens": list(mensagens), "ferramentas": list(ferramentas)})
        for evento in self._roteiro.pop(0):
            yield evento


class FonteLonga:
    """Ticket com dois artigos longos, que gera dois blocos cronológicos."""

    def buscar_por_tn(self, tn: str) -> list[TicketBruto]:
        return [TicketBruto(tn=tn, ticket_id=1, titulo="T", fila="Nivel 1", situacao="aberto")]

    def artigos_do_ticket(self, ticket_id: int) -> list[ArtigoBruto]:
        return [
            ArtigoBruto(1, ticket_id, DATA, True, "A1", "x" * 3000),
            ArtigoBruto(2, ticket_id, DATA, True, "A2", "y" * 3000),
        ]


class BuscaFake:
    def __init__(self, itens: list[ResultadoBusca]) -> None:
        self._itens = itens

    def buscar_lexical(
        self, consulta: str, limite: int = 50, filas: list[str] | None = None
    ) -> list[ResultadoBusca]:
        return self._itens

    def buscar_vetorial(
        self, embedding: list[float], limite: int = 50, filas: list[str] | None = None
    ) -> list[ResultadoBusca]:
        return self._itens

    def similaridades(
        self, embedding: list[float], chaves: list[tuple[str, int, int]]
    ) -> dict[tuple[str, int, int], float]:
        return {chave: 0.9 for chave in chaves}


class EmbeddingsFake:
    def embed(self, textos: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in textos]


class FilasFake:
    def listar_filas(self) -> list[str]:
        return ["Nivel 1", "Nivel 2", "Nivel 3"]


def _chamada(argumentos: str, id_: str = "c1") -> dict[str, Any]:
    return {
        "id": id_,
        "type": "function",
        "function": {"name": "consultar_ticket", "arguments": argumentos},
    }


async def _coletar(agente: Agente, modelo: ModeloFake) -> list[str]:
    return [delta async for delta in agente.stream([{"role": "user", "content": "oi"}], "m")]


async def test_executa_a_ferramenta_e_responde_com_o_resultado() -> None:
    fonte = FonteFake()
    modelo = ModeloFake(
        [
            [EventoFerramentas([_chamada('{"numero":"2026011600004"}')])],
            [EventoTexto("Ticket 2026011600004: ...")],
        ]
    )
    agente = Agente(modelo, [ferramenta_consultar_ticket(fonte)])

    saida = await _coletar(agente, modelo)

    assert saida == ["Ticket 2026011600004: ..."]
    assert fonte.consultados == ["2026011600004"]
    segunda = modelo.chamadas[1]["mensagens"]
    assert any(m["role"] == "tool" and "encontrado" in m["content"] for m in segunda)


async def test_sem_ferramenta_apenas_responde() -> None:
    fonte = FonteFake()
    modelo = ModeloFake([[EventoTexto("Olá!")]])
    agente = Agente(modelo, [ferramenta_consultar_ticket(fonte)])

    saida = await _coletar(agente, modelo)

    assert saida == ["Olá!"]
    assert len(modelo.chamadas) == 1
    assert fonte.consultados == []


async def test_numero_inexistente_vira_resultado_nao_encontrado() -> None:
    fonte = FonteFake(vazio=True)
    modelo = ModeloFake(
        [
            [EventoFerramentas([_chamada('{"numero":"999"}')])],
            [EventoTexto("Não encontrei esse ticket no histórico.")],
        ]
    )
    agente = Agente(modelo, [ferramenta_consultar_ticket(fonte)])

    saida = await _coletar(agente, modelo)

    assert saida == ["Não encontrei esse ticket no histórico."]
    segunda = modelo.chamadas[1]["mensagens"]
    mensagem_tool = next(m for m in segunda if m["role"] == "tool")
    assert "nao_encontrado" in mensagem_tool["content"]


async def test_ticket_extenso_e_resumido_por_blocos() -> None:
    fonte = FonteLonga()
    modelo = ModeloFake(
        [
            [EventoFerramentas([_chamada('{"numero":"1"}')])],
            [EventoTexto("resumo do bloco 1")],
            [EventoTexto("resumo do bloco 2")],
            [EventoTexto("resposta final consolidada")],
        ]
    )
    agente = Agente(modelo, [ferramenta_consultar_ticket(fonte)])

    saida = await _coletar(agente, modelo)

    assert saida == ["resposta final consolidada"]
    assert len(modelo.chamadas) == 4
    final = modelo.chamadas[3]["mensagens"]
    mensagem_tool = next(m for m in final if m["role"] == "tool")
    assert '"cobertura_parcial": true' in mensagem_tool["content"]
    assert '"total_blocos": 2' in mensagem_tool["content"]
    assert '"fontes"' in mensagem_tool["content"]
    assert '"article_id": 1' in mensagem_tool["content"]


def _chamada_de(nome: str, argumentos: str, id_: str = "c1") -> dict[str, Any]:
    return {"id": id_, "type": "function", "function": {"name": nome, "arguments": argumentos}}


async def test_ferramenta_buscar_casos_retorna_fontes() -> None:
    item = ResultadoBusca(
        tn="2026011600004",
        ticket_id=1,
        article_id=5,
        fila="Nivel 2",
        data=DATA,
        visivel_cliente=True,
        posicao=0,
        content="tronco sip sem áudio",
        score=0.0,
    )
    modelo = ModeloFake(
        [
            [
                EventoFerramentas(
                    [_chamada_de("buscar_casos", '{"pergunta":"tronco sip","filas":["Nivel 2"]}')]
                )
            ],
            [EventoTexto("Encontrei casos.")],
        ]
    )
    agente = Agente(modelo, [ferramenta_buscar_casos(BuscaFake([item]), EmbeddingsFake())])
    contexto: dict[str, Any] = {}

    saida = [
        delta
        async for delta in agente.stream([{"role": "user", "content": "tronco cai"}], "m", contexto)
    ]

    assert saida == ["Encontrei casos."]
    tool = next(m for m in modelo.chamadas[1]["mensagens"] if m["role"] == "tool")
    assert "2026011600004" in tool["content"]
    assert contexto["fila_selecionada"] == "Nivel 2"


async def test_resolver_filas_define_a_fila_no_contexto() -> None:
    modelo = ModeloFake(
        [
            [EventoFerramentas([_chamada_de("resolver_filas", '{"texto":"nivel 1"}')])],
            [EventoTexto("ok")],
        ]
    )
    agente = Agente(modelo, [ferramenta_resolver_filas(FilasFake())])
    contexto: dict[str, Any] = {}

    async for _ in agente.stream(
        [{"role": "user", "content": "busque na fila nivel 1"}], "m", contexto
    ):
        pass

    assert contexto["fila_selecionada"] == "Nivel 1"
