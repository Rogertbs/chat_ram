"""Camada de conversa: liga o modelo às ferramentas de Conhecimento OTRS."""

import json
import re
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

from .conhecimento.busca import Embeddings, FonteBusca, FonteFilas, buscar_casos, resolver_filas
from .conhecimento.consulta import FonteTickets, consultar_ticket
from .conhecimento.dominio import StatusConsulta
from .conhecimento.serializacao import casos_para_dicionario, para_dicionario
from .modelo import EventoTexto, ModeloFerramentas
from .persistencia.dominio import EstadoConversa
from .persistencia.repositorio import RepositorioConversas

ROTULO_SUGESTAO = "Sugestão do modelo — não validada no histórico"

SISTEMA = (
    "Você é o assistente que consulta o histórico do OTRS. Regras:\n"
    "- Toda conclusão sobre o histórico deve citar a fonte conferível: número e título "
    "do ticket, data e article_id do trecho usado.\n"
    "- Nunca invente número de ticket, data ou trecho; use apenas o que as ferramentas "
    "retornarem. Se a ferramenta disser que o ticket não existe, informe isso.\n"
    "- Ao consultar um ticket por número, informe a fila dele. A consulta explícita por "
    "número não altera o filtro de fila das buscas seguintes.\n"
    "- Se não houver solução documentada no histórico, declare explicitamente a ausência "
    f'e apresente uma alternativa APENAS sob o rótulo "{ROTULO_SUGESTAO}".\n'
    "- Nunca atribua uma sugestão do modelo aos tickets."
)

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


ESQUEMA_BUSCAR_CASOS: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "buscar_casos",
        "description": (
            "Busca casos semelhantes no histórico pela descrição do problema. Aplica o "
            "filtro de fila informado (ou o selecionado na conversa). Devolve os melhores "
            "trechos com fontes (ticket, fila, article_id, data). Se 'alcance_suficiente' "
            "for falso, declare o alcance da busca e não invente; não apresente trechos "
            "abaixo do threshold como se fossem solução."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pergunta": {"type": "string", "description": "Descrição do problema técnico."},
                "filas": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filas para restringir a busca (opcional).",
                },
            },
            "required": ["pergunta"],
        },
    },
}

ESQUEMA_RESOLVER_FILAS: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "resolver_filas",
        "description": (
            "Resolve o nome de uma fila informado pelo usuário. Devolve os candidatos. "
            "Se 'ambiguo' for verdadeiro, peça esclarecimento ao usuário antes de buscar."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "texto": {"type": "string", "description": "Nome de fila informado pelo usuário."}
            },
            "required": ["texto"],
        },
    },
}


@dataclass(frozen=True)
class Ferramenta:
    """Ferramenta exposta ao modelo: esquema e execução.

    A execução recebe os argumentos e um contexto mutável da conversa
    (fila selecionada, ticket em foco) que as ferramentas podem ler e atualizar.
    """

    nome: str
    esquema: dict[str, Any]
    executar: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


def ferramenta_consultar_ticket(fonte: FonteTickets) -> Ferramenta:
    """Cria a ferramenta `consultar_ticket` sobre uma fonte de tickets."""

    def executar(argumentos: dict[str, Any], contexto: dict[str, Any]) -> dict[str, Any]:
        numero = str(argumentos.get("numero", ""))
        try:
            saida = para_dicionario(consultar_ticket(fonte, numero))
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "falha",
                "ticket": None,
                "mensagem": f"falha técnica ao consultar: {exc}",
            }
        if saida.get("status") == "encontrado" and saida.get("ticket"):
            contexto["ticket_em_foco"] = str(saida["ticket"]["tn"])
        return saida

    return Ferramenta("consultar_ticket", ESQUEMA_CONSULTAR_TICKET, executar)


def ferramenta_buscar_casos(fonte: FonteBusca, embeddings: Embeddings) -> Ferramenta:
    """Cria a ferramenta `buscar_casos` sobre os índices de trechos."""

    def executar(argumentos: dict[str, Any], contexto: dict[str, Any]) -> dict[str, Any]:
        pergunta = str(argumentos.get("pergunta", ""))
        filas = argumentos.get("filas")
        if filas:
            if len(filas) == 1:
                contexto["fila_selecionada"] = str(filas[0])
        elif contexto.get("fila_selecionada"):
            filas = [contexto["fila_selecionada"]]
        try:
            resultado = buscar_casos(fonte, embeddings, pergunta, filas)
        except Exception as exc:  # noqa: BLE001
            return {"status": "falha", "casos": [], "mensagem": f"falha técnica na busca: {exc}"}
        return casos_para_dicionario(resultado)

    return Ferramenta("buscar_casos", ESQUEMA_BUSCAR_CASOS, executar)


def ferramenta_resolver_filas(fonte: FonteFilas) -> Ferramenta:
    """Cria a ferramenta `resolver_filas` sobre a lista de filas do OTRS."""

    def executar(argumentos: dict[str, Any], contexto: dict[str, Any]) -> dict[str, Any]:
        resultado = resolver_filas(fonte.listar_filas(), str(argumentos.get("texto", "")))
        if len(resultado.candidatos) == 1 and not resultado.ambiguo:
            contexto["fila_selecionada"] = resultado.candidatos[0]
        return {"candidatos": list(resultado.candidatos), "ambiguo": resultado.ambiguo}

    return Ferramenta("resolver_filas", ESQUEMA_RESOLVER_FILAS, executar)


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
        contexto: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        """Produz os deltas da resposta, executando ferramentas se o modelo pedir."""
        conversa = list(mensagens)
        contexto = contexto if contexto is not None else {}
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
            saida = await self._compactar(self._executar(chamada, contexto), modelo)
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

    def _executar(self, chamada: dict[str, Any], contexto: dict[str, Any]) -> dict[str, Any]:
        funcao = chamada.get("function") or {}
        nome = str(funcao.get("name", ""))
        ferramenta = self._por_nome.get(nome)
        if ferramenta is None:
            return {
                "status": "falha",
                "ticket": None,
                "mensagem": f"ferramenta desconhecida: {nome}",
            }
        return ferramenta.executar(_argumentos(funcao.get("arguments")), contexto)

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
            resumos.append(
                {
                    "indice_inicial": bloco["indice_inicial"],
                    "article_ids": list(bloco["article_ids"]),
                    "fontes": [
                        {"article_id": article_id, "data": artigos[article_id]["data"]}
                        for article_id in bloco["article_ids"]
                        if article_id in artigos
                    ],
                    "resumo": "".join(pedacos),
                }
            )
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
        fonte_tickets: FonteTickets | None = None,
    ) -> None:
        self._agente = agente
        self._conversas = conversas
        self._nome_modelo = nome_modelo
        self._fonte_tickets = fonte_tickets

    async def stream(
        self, chat_id: str, request_id: str, mensagens: list[dict[str, Any]]
    ) -> AsyncIterator[str]:
        """Responde à nova mensagem, restaurando o histórico e o estado persistidos."""
        thread_id = self._conversas.resolver_thread(chat_id)
        historico = self._conversas.carregar_mensagens(thread_id)
        estado = self._conversas.carregar_estado(thread_id)
        nova = _ultima_mensagem(mensagens)
        nova_inserida = self._conversas.salvar_mensagem(
            thread_id, request_id, "user", str(nova["content"])
        )
        if not nova_inserida:
            resposta = self._conversas.carregar_resposta(thread_id, request_id)
            if resposta is not None:
                yield resposta
                return

        entrada: list[dict[str, Any]] = [{"role": "system", "content": SISTEMA}]
        mensagem_estado = _contexto_estado(estado)
        if mensagem_estado is not None:
            entrada.append(mensagem_estado)
        if (
            self._fonte_tickets is not None
            and estado.ticket_em_foco
            and not _menciona_numero(str(nova["content"]))
        ):
            foco = _contexto_ticket(self._fonte_tickets, estado.ticket_em_foco)
            if foco is not None:
                entrada.append(foco)
        entrada.extend(historico)
        if nova_inserida:
            entrada.append(nova)

        contexto: dict[str, Any] = {
            "fila_selecionada": estado.fila_selecionada,
            "ticket_em_foco": estado.ticket_em_foco,
        }
        pedacos: list[str] = []
        async for delta in self._agente.stream(entrada, self._nome_modelo, contexto):
            pedacos.append(delta)
            yield delta
        self._conversas.salvar_mensagem(thread_id, request_id, "assistant", "".join(pedacos))
        if (
            contexto.get("fila_selecionada") != estado.fila_selecionada
            or contexto.get("ticket_em_foco") != estado.ticket_em_foco
        ):
            estado.fila_selecionada = contexto.get("fila_selecionada")
            estado.ticket_em_foco = contexto.get("ticket_em_foco")
            self._conversas.salvar_estado(thread_id, estado)


LIMITE_CONTEXTO_TICKET = 8000


def _contexto_ticket(fonte: FonteTickets, tn: str) -> dict[str, Any] | None:
    """Monta o conteúdo do ticket em foco como contexto, com as fontes."""
    resultado = consultar_ticket(fonte, tn)
    if resultado.status != StatusConsulta.ENCONTRADO or resultado.ticket is None:
        return None
    ticket = resultado.ticket
    partes = [
        f"Ticket {ticket.tn} — {ticket.titulo} (fila {ticket.fila}, situação {ticket.situacao})"
    ]
    for artigo in ticket.artigos:
        partes.append(
            f"[article_id={artigo.article_id} data={artigo.data.isoformat()} "
            f"visivel_cliente={artigo.visivel_cliente}] {artigo.assunto}\n{artigo.corpo}"
        )
    texto = "\n\n".join(partes)
    if len(texto) > LIMITE_CONTEXTO_TICKET:
        texto = texto[:LIMITE_CONTEXTO_TICKET] + "\n\n[cobertura parcial do ticket em foco]"
    return {
        "role": "system",
        "content": (
            "Conteúdo do ticket em foco (contexto para perguntas seguintes; cite as fontes):\n"
            + texto
        ),
    }


def _menciona_numero(texto: str) -> bool:
    return re.search(r"\d{10,}", texto) is not None


def _contexto_estado(estado: EstadoConversa) -> dict[str, Any] | None:
    partes = []
    if estado.fila_selecionada:
        partes.append(f"fila selecionada: {estado.fila_selecionada}")
    if estado.ticket_em_foco:
        partes.append(f"ticket em foco: {estado.ticket_em_foco}")
    if estado.esclarecimentos:
        partes.append("esclarecimentos pendentes: " + "; ".join(estado.esclarecimentos))
    if not partes:
        return None
    return {
        "role": "system",
        "content": "Estado da conversa (persistido): " + "; ".join(partes) + ".",
    }


def _ultima_mensagem(mensagens: list[dict[str, Any]]) -> dict[str, Any]:
    for mensagem in reversed(mensagens):
        if mensagem.get("role") == "user":
            return {"role": "user", "content": mensagem.get("content", "")}
    return {"role": "user", "content": mensagens[-1].get("content", "") if mensagens else ""}
