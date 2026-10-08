"""Adapter ao proxy LiteLLM: expõe os deltas de texto e as chamadas de ferramenta."""

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol

import httpx


@dataclass(frozen=True)
class EventoTexto:
    """Delta de texto produzido pelo modelo."""

    texto: str


@dataclass(frozen=True)
class EventoFerramentas:
    """Chamadas de ferramenta acumuladas ao fim do stream."""

    chamadas: list[dict[str, Any]]


EventoModelo = EventoTexto | EventoFerramentas


class Modelo(Protocol):
    """Fonte de geração de texto. Adapter do proxy LiteLLM."""

    def stream(self, mensagens: list[dict[str, Any]], modelo: str) -> AsyncIterator[str]:
        """Produz os deltas de texto da resposta, em ordem."""
        ...


class ModeloFerramentas(Protocol):
    """Modelo que também decide chamadas de ferramenta."""

    def stream_eventos(
        self,
        mensagens: list[dict[str, Any]],
        ferramentas: list[dict[str, Any]],
        modelo: str,
    ) -> AsyncIterator[EventoModelo]:
        """Produz deltas de texto e, ao fim, as chamadas de ferramenta pedidas."""
        ...


class LiteLLMModel:
    """Consome /v1/chat/completions do LiteLLM em modo streaming."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 120.0) -> None:
        self._url = f"{base_url.rstrip('/')}/v1/chat/completions"
        self._api_key = api_key
        self._timeout = timeout

    async def stream(self, mensagens: list[dict[str, Any]], modelo: str) -> AsyncIterator[str]:
        async for evento in self.stream_eventos(mensagens, [], modelo):
            if isinstance(evento, EventoTexto):
                yield evento.texto

    async def stream_eventos(
        self,
        mensagens: list[dict[str, Any]],
        ferramentas: list[dict[str, Any]],
        modelo: str,
    ) -> AsyncIterator[EventoModelo]:
        payload: dict[str, Any] = {"model": modelo, "messages": mensagens, "stream": True}
        if ferramentas:
            payload["tools"] = ferramentas
        headers = {"Authorization": f"Bearer {self._api_key}"}
        acumulado: dict[int, dict[str, Any]] = {}
        async with (
            httpx.AsyncClient(timeout=self._timeout) as client,
            client.stream("POST", self._url, json=payload, headers=headers) as resposta,
        ):
            resposta.raise_for_status()
            async for linha in resposta.aiter_lines():
                objeto = _objeto_de_linha(linha)
                if objeto is None:
                    continue
                escolhas = objeto.get("choices") or []
                if not escolhas:
                    continue
                delta = escolhas[0].get("delta", {})
                conteudo = delta.get("content")
                if conteudo:
                    yield EventoTexto(conteudo)
                for chamada in delta.get("tool_calls") or []:
                    _acumular_chamada(acumulado, chamada)
        if acumulado:
            yield EventoFerramentas([acumulado[i] for i in sorted(acumulado)])


def _objeto_de_linha(linha: str) -> dict[str, Any] | None:
    """Extrai o objeto JSON de uma linha SSE do LiteLLM."""
    if not linha.startswith("data:"):
        return None
    dados = linha.removeprefix("data:").strip()
    if not dados or dados == "[DONE]":
        return None
    try:
        objeto = json.loads(dados)
    except json.JSONDecodeError:
        return None
    if not isinstance(objeto, dict):
        return None
    if "error" in objeto:
        raise RuntimeError(objeto["error"].get("message", "erro do proxy"))
    return dict(objeto)


def _acumular_chamada(acumulado: dict[int, dict[str, Any]], chamada: dict[str, Any]) -> None:
    indice = int(chamada.get("index", 0))
    atual = acumulado.setdefault(
        indice,
        {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
    )
    if chamada.get("id"):
        atual["id"] = chamada["id"]
    funcao = chamada.get("function") or {}
    if funcao.get("name"):
        atual["function"]["name"] = funcao["name"]
    if funcao.get("arguments"):
        atual["function"]["arguments"] += funcao["arguments"]
