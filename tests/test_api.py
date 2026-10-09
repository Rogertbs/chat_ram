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
    cfg = Settings(
        litellm_base_url="http://proxy",
        litellm_api_key="sk",
        model_alias="alvo",
        chat_ram_api_key=None,
    )
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


class ConversaFake:
    def __init__(self) -> None:
        self.chamadas: list[tuple[str, str]] = []

    async def stream(
        self, chat_id: str, request_id: str, mensagens: list[dict[str, str]]
    ) -> AsyncIterator[str]:
        self.chamadas.append((chat_id, request_id))
        yield "ok"


async def test_encaminha_o_identificador_de_conversa() -> None:
    cfg = Settings(
        litellm_base_url="http://proxy",
        litellm_api_key="sk",
        model_alias="alvo",
        chat_ram_api_key=None,
    )
    conversa = ConversaFake()
    app = create_app(ModeloFake([]), cfg, None, conversa)  # type: ignore[arg-type]
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://teste") as client:
        resposta = await client.post(
            "/v1/chat/completions",
            json=PEDIDO,
            headers={"x-conversation-id": "chat-9", "x-request-id": "req-9"},
        )

    assert resposta.status_code == 200
    assert resposta.headers["x-conversation-id"] == "chat-9"
    assert conversa.chamadas == [("chat-9", "req-9")]


async def test_exige_api_key_quando_configurada() -> None:
    cfg = Settings(
        litellm_base_url="http://proxy",
        litellm_api_key="sk",
        model_alias="alvo",
        chat_ram_api_key="segredo",
    )
    app = create_app(ModeloFake(["ok"]), cfg)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://teste") as client:
        sem_chave = await client.post("/v1/chat/completions", json=PEDIDO)
        chave_errada = await client.post(
            "/v1/chat/completions", json=PEDIDO, headers={"authorization": "Bearer errada"}
        )
        chave_certa = await client.post(
            "/v1/chat/completions", json=PEDIDO, headers={"authorization": "Bearer segredo"}
        )
        saude = await client.get("/health")

    assert sem_chave.status_code == 401
    assert chave_errada.status_code == 401
    assert chave_certa.status_code == 200
    assert saude.status_code == 200


class GuardrailFake:
    def __init__(self, no_escopo: bool) -> None:
        self._no_escopo = no_escopo

    async def esta_no_escopo(self, mensagens: list[dict[str, str]], modelo: str) -> bool:
        return self._no_escopo


async def test_guardrail_endpoint_sinaliza_fora_do_escopo() -> None:
    cfg = Settings(
        litellm_base_url="http://proxy",
        litellm_api_key="sk",
        model_alias="alvo",
        chat_ram_api_key="segredo",
    )
    app = create_app(ModeloFake([]), cfg, None, None, GuardrailFake(no_escopo=False))
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://teste") as client:
        fora = await client.post(
            "/guardrail",
            json={"input": "receita de bolo"},
            headers={"authorization": "Bearer segredo"},
        )
        sem_chave = await client.post("/guardrail", json={"input": "receita de bolo"})

    assert fora.status_code == 200
    assert fora.json()["flagged"] is True
    assert "helpdesk" in fora.json()["mensagem"]
    assert sem_chave.status_code == 401


async def test_usa_chat_id_do_metadata_da_open_webui() -> None:
    cfg = Settings(
        litellm_base_url="http://proxy",
        litellm_api_key="sk",
        model_alias="alvo",
        chat_ram_api_key=None,
    )
    conversa = ConversaFake()
    app = create_app(ModeloFake([]), cfg, None, conversa)  # type: ignore[arg-type]
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://teste") as client:
        resposta = await client.post(
            "/v1/chat/completions",
            json={**PEDIDO, "metadata": {"chat_id": "chat-meta", "message_id": "msg-1"}},
        )

    assert resposta.status_code == 200
    assert resposta.headers["x-conversation-id"] == "chat-meta"
    assert conversa.chamadas == [("chat-meta", "msg-1")]
