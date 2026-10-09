from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from chat_ram.conhecimento.dominio import ArtigoBruto, TicketBruto
from chat_ram.conversa import Conversa
from chat_ram.persistencia.dominio import EstadoConversa

DATA = datetime(2026, 1, 1, tzinfo=UTC)


class RepoFake:
    def __init__(self) -> None:
        self.chats: dict[str, str] = {}
        self.mensagens: dict[str, list[dict[str, str]]] = {}
        self.estados: dict[str, EstadoConversa] = {}
        self._seq = 0

    def resolver_thread(self, chat_id: str) -> str:
        if chat_id not in self.chats:
            self._seq += 1
            self.chats[chat_id] = f"t{self._seq}"
        return self.chats[chat_id]

    def carregar_mensagens(self, thread_id: str) -> list[dict[str, str]]:
        return [
            {"role": m["role"], "content": m["content"]} for m in self.mensagens.get(thread_id, [])
        ]

    def salvar_mensagem(self, thread_id: str, request_id: str, papel: str, conteudo: str) -> bool:
        lista = self.mensagens.setdefault(thread_id, [])
        if any(m["req"] == request_id and m["role"] == papel for m in lista):
            return False
        lista.append({"role": papel, "content": conteudo, "req": request_id})
        return True

    def carregar_resposta(
        self, thread_id: str, request_id: str, papel: str = "assistant"
    ) -> str | None:
        for mensagem in self.mensagens.get(thread_id, []):
            if mensagem["req"] == request_id and mensagem["role"] == papel:
                return mensagem["content"]
        return None

    def carregar_estado(self, thread_id: str) -> EstadoConversa:
        return self.estados.get(thread_id, EstadoConversa())

    def salvar_estado(self, thread_id: str, estado: EstadoConversa) -> None:
        self.estados[thread_id] = estado


class FonteTicketsFake:
    def buscar_por_tn(self, tn: str) -> list[TicketBruto]:
        return [
            TicketBruto(tn=tn, ticket_id=1, titulo="Tronco SIP", fila="Nivel 2", situacao="aberto")
        ]

    def artigos_do_ticket(self, ticket_id: int) -> list[ArtigoBruto]:
        return [ArtigoBruto(6, ticket_id, DATA, True, "Assunto", "Corpo do ticket")]


class AgenteFake:
    def __init__(self, ticket: str | None = None, deltas: tuple[str, ...] = ("ok",)) -> None:
        self._ticket = ticket
        self._deltas = deltas
        self.recebidas: list[list[dict[str, Any]]] = []

    async def stream(
        self,
        mensagens: list[dict[str, Any]],
        modelo: str,
        contexto: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        self.recebidas.append([dict(m) for m in mensagens])
        if contexto is not None and self._ticket is not None:
            contexto["ticket_em_foco"] = self._ticket
        for delta in self._deltas:
            yield delta


async def _responder(conversa: Conversa, chat: str, req: str, texto: str) -> str:
    return "".join(
        [d async for d in conversa.stream(chat, req, [{"role": "user", "content": texto}])]
    )


async def test_retomar_restaura_o_historico() -> None:
    repo = RepoFake()
    agente = AgenteFake()
    conversa = Conversa(agente, repo, "m")  # type: ignore[arg-type]

    await _responder(conversa, "chat1", "r1", "oi")
    await _responder(conversa, "chat1", "r2", "e o ticket 123?")

    segunda = [m for m in agente.recebidas[1] if m["role"] != "system"]
    assert [m["role"] for m in segunda] == ["user", "assistant", "user"]
    assert segunda[0]["content"] == "oi"
    assert segunda[2]["content"] == "e o ticket 123?"


async def test_duas_conversas_nao_vazam_contexto() -> None:
    repo = RepoFake()
    agente = AgenteFake()
    conversa = Conversa(agente, repo, "m")  # type: ignore[arg-type]

    await _responder(conversa, "chatA", "r1", "assunto A")
    await _responder(conversa, "chatB", "r2", "assunto B")

    assert repo.chats["chatA"] != repo.chats["chatB"]
    recebidas_b = [m for m in agente.recebidas[1] if m["role"] != "system"]
    assert [m["content"] for m in recebidas_b] == ["assunto B"]


async def test_identificador_estavel_e_ligado_ao_thread() -> None:
    repo = RepoFake()
    conversa = Conversa(AgenteFake(), repo, "m")  # type: ignore[arg-type]

    await _responder(conversa, "chat1", "r1", "oi")
    await _responder(conversa, "chat1", "r2", "de novo")

    assert repo.chats == {"chat1": "t1"}


async def test_retentativa_da_mesma_requisicao_nao_duplica() -> None:
    repo = RepoFake()
    agente = AgenteFake()
    conversa = Conversa(agente, repo, "m")  # type: ignore[arg-type]

    primeira = await _responder(conversa, "chat1", "req-x", "oi")
    segunda = await _responder(conversa, "chat1", "req-x", "oi")

    mensagens = repo.mensagens["t1"]
    assert [m["role"] for m in mensagens] == ["user", "assistant"]
    assert len(agente.recebidas) == 1
    assert segunda == primeira


async def test_estado_persistido_entra_no_contexto_ao_retomar() -> None:
    repo = RepoFake()
    repo.estados["t1"] = EstadoConversa(
        fila_selecionada="Infraestrutura", ticket_em_foco="2026011600004"
    )
    agente = AgenteFake()
    conversa = Conversa(agente, repo, "m")  # type: ignore[arg-type]

    await _responder(conversa, "chat1", "r1", "e aí?")

    sistema = [m for m in agente.recebidas[0] if m["role"] == "system"]
    texto = " ".join(m["content"] for m in sistema)
    assert "ticket em foco: 2026011600004" in texto
    assert "fila selecionada: Infraestrutura" in texto


async def test_ticket_em_foco_e_persistido() -> None:
    repo = RepoFake()
    conversa = Conversa(AgenteFake(ticket="2026011600004"), repo, "m")  # type: ignore[arg-type]

    await _responder(conversa, "chat1", "r1", "veja o ticket 2026011600004")

    assert repo.estados["t1"].ticket_em_foco == "2026011600004"


async def test_sistema_traz_as_regras_e_o_rotulo_da_sugestao() -> None:
    agente = AgenteFake()
    conversa = Conversa(agente, RepoFake(), "m")  # type: ignore[arg-type]

    await _responder(conversa, "chat1", "r1", "oi")

    sistema = agente.recebidas[0][0]
    assert sistema["role"] == "system"
    assert "Sugestão do modelo — não validada no histórico" in sistema["content"]
    assert "nunca invente" in sistema["content"].lower()
    assert "escopo estrito" in sistema["content"].lower()


async def test_pergunta_seguinte_usa_o_conteudo_do_ticket_em_foco() -> None:
    repo = RepoFake()
    repo.estados["t1"] = EstadoConversa(ticket_em_foco="2026011600004")
    agente = AgenteFake()
    conversa = Conversa(agente, repo, "m", fonte_tickets=FonteTicketsFake())  # type: ignore[arg-type]

    await _responder(conversa, "chat1", "r1", "e qual foi a solução?")

    sistema = " ".join(m["content"] for m in agente.recebidas[0] if m["role"] == "system")
    assert "Corpo do ticket" in sistema
    assert "article_id=6" in sistema


async def test_consulta_com_numero_nao_injeta_o_foco() -> None:
    repo = RepoFake()
    repo.estados["t1"] = EstadoConversa(ticket_em_foco="2026011600004")
    agente = AgenteFake()
    conversa = Conversa(agente, repo, "m", fonte_tickets=FonteTicketsFake())  # type: ignore[arg-type]

    await _responder(conversa, "chat1", "r1", "consulte o ticket 2026011900010")

    sistema = " ".join(m["content"] for m in agente.recebidas[0] if m["role"] == "system")
    assert "Corpo do ticket" not in sistema


async def test_usa_historico_da_ui_quando_nao_ha_persistido() -> None:
    repo = RepoFake()
    agente = AgenteFake()
    conversa = Conversa(agente, repo, "m")  # type: ignore[arg-type]
    mensagens = [
        {"role": "user", "content": "oi"},
        {"role": "assistant", "content": "olá"},
        {"role": "user", "content": "e agora?"},
    ]

    async for _ in conversa.stream("chat1", "r1", mensagens):
        pass

    recebidas = [m for m in agente.recebidas[0] if m["role"] != "system"]
    assert [m["content"] for m in recebidas] == ["oi", "olá", "e agora?"]


class GuardrailFake:
    def __init__(self, permitir: bool) -> None:
        self._permitir = permitir
        self.chamadas = 0

    async def esta_no_escopo(self, mensagens: list[dict[str, Any]], modelo: str) -> bool:
        self.chamadas += 1
        return self._permitir


async def test_guardrail_bloqueia_fora_do_escopo() -> None:
    repo = RepoFake()
    agente = AgenteFake()
    guardrail = GuardrailFake(permitir=False)
    conversa = Conversa(agente, repo, "m", guardrail=guardrail)  # type: ignore[arg-type]

    saida = await _responder(conversa, "chat1", "r1", "me dê uma receita de bolo")

    assert "helpdesk" in saida
    assert agente.recebidas == []
    assert guardrail.chamadas == 1
    assert [m["role"] for m in repo.mensagens["t1"]] == ["user", "assistant"]


async def test_guardrail_libera_dentro_do_escopo() -> None:
    repo = RepoFake()
    agente = AgenteFake()
    guardrail = GuardrailFake(permitir=True)
    conversa = Conversa(agente, repo, "m", guardrail=guardrail)  # type: ignore[arg-type]

    saida = await _responder(conversa, "chat1", "r1", "consulte o ticket 123")

    assert saida == "ok"
    assert len(agente.recebidas) == 1
