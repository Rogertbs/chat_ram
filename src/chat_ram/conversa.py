"""Camada de conversa: liga o modelo às ferramentas de Conhecimento OTRS."""

import json
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

from .conhecimento.consulta import FonteTickets, consultar_ticket
from .conhecimento.serializacao import para_dicionario
from .modelo import EventoTexto, ModeloFerramentas
from .persistencia.repositorio import RepositorioConversas

ESQUEMA_CONSULTAR_TICKET: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "consultar_ticket",
        "description": (
            "Consulta um ticket do OTRS pelo número público exato. Devolve fila, "
            "situação e os artigos em ordem cronológica, cada um com article_id, data "
            "e visibilidade. Use sempre que o usuário informar um número de ticket. "
            "Se o status for 'nao_encontrado', informe que o ticket não existe no "
            "histórico; nunca invente um ticket."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "numero": {
                    "type": "string",
                    "description": "Número público do ticket (tn), apenas dígitos.",
                }
            },
            "required": ["numero"],
        },
    },
}


@dataclass(frozen=True)
class Ferramenta:
    """Ferramenta exposta ao modelo: esquema e execução."""

    nome: str
    esquema: dict[str, Any]
    executar: Callable[[dict[str, Any]], dict[str, Any]]


def ferramenta_consultar_ticket(fonte: FonteTickets) -> Ferramenta:
    """Cria a ferramenta `consultar_ticket` sobre uma fonte de tickets."""

    def executar(argumentos: dict[str, Any]) -> dict[str, Any]:
        numero = str(argumentos.get("numero", ""))
        try:
            return para_dicionario(consultar_ticket(fonte, numero))
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "falha",
                "ticket": None,
                "mensagem": f"falha técnica ao consultar: {exc}",
            }

    return Ferramenta("consultar_ticket", ESQUEMA_CONSULTAR_TICKET, executar)


class Agente:
    """Executa uma rodada de ferramentas quando o modelo pede e então responde."""

    def __init__(self, modelo: ModeloFerramentas, ferramentas: list[Ferramenta]) -> None:
        self._modelo = modelo
        self._ferramentas = ferramentas
        self._por_nome = {ferramenta.nome: ferramenta for ferramenta in ferramentas}

    @property
    def esquemas(self) -> list[dict[str, Any]]:
        return [ferramenta.esquema for ferramenta in self._ferramentas]

    async def stream(
        self,
        mensagens: list[dict[str, Any]],
        modelo: str,
        ao_ferramenta: Callable[[dict[str, Any]], None] | None = None,
    ) -> AsyncIterator[str]:
        """Produz os deltas da resposta, executando ferramentas se o modelo pedir."""
        conversa = list(mensagens)
        chamadas: list[dict[str, Any]] = []
        async for evento in self._modelo.stream_eventos(conversa, self.esquemas, modelo):
            if isinstance(evento, EventoTexto):
                yield evento.texto
            else:
                chamadas = evento.chamadas
        if not chamadas:
            return

        conversa.append({"role": "assistant", "content": "", "tool_calls": chamadas})
        for chamada in chamadas:
            saida = self._executar(chamada)
            if ao_ferramenta is not None:
                ao_ferramenta(saida)
            saida = await self._compactar(saida, modelo)
            conversa.append(
                {
                    "role": "tool",
                    "tool_call_id": str(chamada.get("id", "")),
                    "content": json.dumps(saida, ensure_ascii=False),
                }
            )
        async for evento in self._modelo.stream_eventos(conversa, [], modelo):
            if isinstance(evento, EventoTexto):
                yield evento.texto

    def _executar(self, chamada: dict[str, Any]) -> dict[str, Any]:
        funcao = chamada.get("function") or {}
        nome = str(funcao.get("name", ""))
        ferramenta = self._por_nome.get(nome)
        if ferramenta is None:
            return {
                "status": "falha",
                "ticket": None,
                "mensagem": f"ferramenta desconhecida: {nome}",
            }
        return ferramenta.executar(_argumentos(funcao.get("arguments")))

    async def _compactar(self, saida: dict[str, Any], modelo: str) -> dict[str, Any]:
        """Resume tickets extensos em blocos cronológicos antes da resposta final."""
        ticket = saida.get("ticket")
        if saida.get("status") != "encontrado" or not ticket or not ticket.get("cobertura_parcial"):
            return saida
        artigos = {artigo["article_id"]: artigo for artigo in ticket["artigos"]}
        resumos = []
        for bloco in ticket["blocos"]:
            corpo = "\n\n".join(
                _texto_artigo(artigos[article_id], ticket)
                for article_id in bloco["article_ids"]
                if article_id in artigos
            )
            mensagens = [
                {
                    "role": "system",
                    "content": (
                        "Resuma cronologicamente os artigos abaixo do ticket, "
                        "preservando as fontes (article_id e data). Não invente fatos."
                    ),
                },
                {"role": "user", "content": corpo},
            ]
            pedacos = [
                evento.texto
                async for evento in self._modelo.stream_eventos(mensagens, [], modelo)
                if isinstance(evento, EventoTexto)
            ]
            resumos.append({"indice_inicial": bloco["indice_inicial"], "resumo": "".join(pedacos)})
        return {
            "status": "encontrado",
            "ticket": {
                "tn": ticket["tn"],
                "titulo": ticket["titulo"],
                "fila": ticket["fila"],
                "situacao": ticket["situacao"],
                "cobertura_parcial": True,
                "total_blocos": len(resumos),
                "resumos_por_bloco": resumos,
            },
        }


def _texto_artigo(artigo: dict[str, Any], ticket: dict[str, Any]) -> str:
    cabecalho = (
        f"[article_id={artigo['article_id']} data={artigo['data']} "
        f"visivel_cliente={artigo['visivel_cliente']}]"
    )
    return f"{cabecalho}\n{artigo['assunto']}\n{artigo['corpo']}"


def _argumentos(texto: object) -> dict[str, Any]:
    if not isinstance(texto, str) or not texto.strip():
        return {}
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError:
        return {}
    return dados if isinstance(dados, dict) else {}


class Conversa:
    """Persiste mensagens e estado por thread_id e responde com o agente."""

    def __init__(
        self,
        agente: Agente,
        conversas: RepositorioConversas,
        nome_modelo: str,
    ) -> None:
        self._agente = agente
        self._conversas = conversas
        self._nome_modelo = nome_modelo

    async def stream(
        self, chat_id: str, request_id: str, mensagens: list[dict[str, Any]]
    ) -> AsyncIterator[str]:
        """Responde à nova mensagem, restaurando o histórico persistido do chat."""
        thread_id = self._conversas.resolver_thread(chat_id)
        historico = self._conversas.carregar_mensagens(thread_id)
        nova = _ultima_mensagem(mensagens)
        self._conversas.salvar_mensagem(thread_id, request_id, "user", str(nova["content"]))

        ticket_em_foco: list[str] = []

        def ao_ferramenta(saida: dict[str, Any]) -> None:
            ticket = saida.get("ticket")
            if saida.get("status") == "encontrado" and ticket:
                ticket_em_foco.append(str(ticket["tn"]))

        pedacos: list[str] = []
        entrada = [*historico, nova]
        async for delta in self._agente.stream(entrada, self._nome_modelo, ao_ferramenta):
            pedacos.append(delta)
            yield delta
        self._conversas.salvar_mensagem(thread_id, request_id, "assistant", "".join(pedacos))
        if ticket_em_foco:
            estado = self._conversas.carregar_estado(thread_id)
            estado.ticket_em_foco = ticket_em_foco[-1]
            self._conversas.salvar_estado(thread_id, estado)


def _ultima_mensagem(mensagens: list[dict[str, Any]]) -> dict[str, Any]:
    for mensagem in reversed(mensagens):
        if mensagem.get("role") == "user":
            return {"role": "user", "content": mensagem.get("content", "")}
    return {"role": "user", "content": mensagens[-1].get("content", "") if mensagens else ""}
