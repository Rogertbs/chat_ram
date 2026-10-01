"""Adapter ao proxy LiteLLM: expõe os deltas de texto de uma resposta."""

import json
from collections.abc import AsyncIterator
from typing import Protocol

import httpx


class Modelo(Protocol):
    """Fonte de geração de texto. Adapter do proxy LiteLLM."""

    def stream(self, mensagens: list[dict[str, str]], modelo: str) -> AsyncIterator[str]:
        """Produz os deltas de texto da resposta, em ordem."""
        ...


class LiteLLMModel:
    """Consome /v1/chat/completions do LiteLLM em modo streaming."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 120.0) -> None:
        self._url = f"{base_url.rstrip('/')}/v1/chat/completions"
        self._api_key = api_key
        self._timeout = timeout

    async def stream(self, mensagens: list[dict[str, str]], modelo: str) -> AsyncIterator[str]:
        payload = {"model": modelo, "messages": mensagens, "stream": True}
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with (
            httpx.AsyncClient(timeout=self._timeout) as client,
            client.stream("POST", self._url, json=payload, headers=headers) as resposta,
        ):
            resposta.raise_for_status()
            async for linha in resposta.aiter_lines():
                delta = _delta_de_linha(linha)
                if delta:
                    yield delta


def _delta_de_linha(linha: str) -> str | None:
    """Extrai o delta de conteúdo de uma linha SSE do LiteLLM."""
    if not linha.startswith("data:"):
        return None
    dados = linha.removeprefix("data:").strip()
    if not dados or dados == "[DONE]":
        return None
    try:
        objeto = json.loads(dados)
    except json.JSONDecodeError:
        return None
    if "error" in objeto:
        raise RuntimeError(objeto["error"].get("message", "erro do proxy"))
    escolhas = objeto.get("choices") or []
    if not escolhas:
        return None
    conteudo = escolhas[0].get("delta", {}).get("content")
    return conteudo or None
