import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
from fastapi import FastAPI
from httpx import ASGITransport

from chat_ram.api import create_app
from chat_ram.config import Settings


class ModeloFake:
    """Adapter de teste que produz deltas fixos e, opcionalmente, falha no fim."""

    def __init__(self, deltas: list[str], falha: bool = False) -> None:
        self._deltas = deltas
        self._falha = falha

    async def stream(self, mensagens: list[dict[str, str]], modelo: str) -> AsyncIterator[str]:
        for delta in self._deltas:
            yield delta
        if self._falha:
            raise RuntimeError("proxy caiu")


def _app(modelo: ModeloFake) -> FastAPI:
    cfg = Settings(litellm_base_url="http://proxy", litellm_api_key="sk", model_alias="alvo")
    return create_app(modelo, cfg)


async def _post(app: FastAPI, payload: dict[str, Any]) -> httpx.Response:
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://teste") as client:
        return await client.post("/v1/chat/completions", json=payload)


PEDIDO: dict[str, Any] = {"messages": [{"role": "user", "content": "oi"}]}


async def test_resposta_completa_sem_stream() -> None:
    resposta = await _post(_app(ModeloFake(["Olá", ", mundo"])), PEDIDO)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["object"] == "chat.completion"
    assert corpo["choices"][0]["message"]["content"] == "Olá, mundo"


async def test_stream_entrega_sse_ordenado_com_fim() -> None:
    resposta = await _post(_app(ModeloFake(["Olá", " mundo"])), {**PEDIDO, "stream": True})

    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("text/event-stream")
    texto = resposta.text
    assert '"Olá"' in texto
    assert '" mundo"' in texto
    assert texto.rstrip().endswith("data: [DONE]")
    linhas = [linha for linha in texto.splitlines() if linha.startswith("data:")]
    ultimo_delta = json.loads(linhas[-2].removeprefix("data: "))
    assert ultimo_delta["choices"][0]["finish_reason"] == "stop"


async def test_falha_do_proxy_sem_stream_retorna_502() -> None:
    resposta = await _post(_app(ModeloFake(["x"], falha=True)), PEDIDO)

    assert resposta.status_code == 502
    assert resposta.json()["error"]["type"] == "upstream_error"


async def test_falha_no_stream_encerra_sem_travar() -> None:
    resposta = await _post(_app(ModeloFake(["Olá"], falha=True)), {**PEDIDO, "stream": True})

    assert resposta.status_code == 200
    assert '"upstream_error"' in resposta.text
    assert resposta.text.rstrip().endswith("data: [DONE]")


async def test_lista_modelos() -> None:
    app = _app(ModeloFake([]))
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://teste") as client:
        resposta = await client.get("/v1/models")

    assert resposta.status_code == 200
    assert resposta.json()["data"][0]["id"] == "alvo"
