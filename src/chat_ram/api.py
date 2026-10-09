"""Endpoint HTTP OpenAI-compatible para a Open WebUI."""

import hmac
import json
import logging
import re
import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from .config import Settings
from .conversa import RECUSA_ESCOPO, ClassificadorEscopo, Conversa
from .modelo import Modelo

_logger = logging.getLogger(__name__)

# Marcador que o filtro da Open WebUI injeta na última mensagem com o id da conversa.
_MARCADOR_CONVERSA = re.compile(r"\[\[chat_ram_id:([^\]\s]+)\]\]")


class Mensagem(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str | None = None
    messages: list[Mensagem]
    stream: bool = False
    # A Open WebUI encaminha metadados (chat_id, message_id, session_id) no corpo.
    metadata: dict[str, Any] | None = None


class GuardrailRequest(BaseModel):
    input: str


def create_app(
    modelo: Modelo,
    settings: Settings,
    agente: Modelo | None = None,
    conversa: Conversa | None = None,
    guardrail: ClassificadorEscopo | None = None,
) -> FastAPI:
    app = FastAPI(title="chat_ram")

    def verificar_api_key(request: Request) -> None:
        """Exige `Authorization: Bearer <chave>` quando uma chave está configurada."""
        if not settings.chat_ram_api_key:
            return
        cabecalho = request.headers.get("authorization", "")
        if not hmac.compare_digest(
            cabecalho.encode(), f"Bearer {settings.chat_ram_api_key}".encode()
        ):
            raise HTTPException(status_code=401, detail="chave de API ausente ou inválida")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/guardrail", dependencies=[Depends(verificar_api_key)])
    async def guardrail_endpoint(req: GuardrailRequest) -> dict[str, Any]:
        """Classifica o texto como dentro/fora do escopo (usado pela moderação da UI)."""
        if guardrail is None:
            return {"flagged": False, "mensagem": ""}
        no_escopo = await guardrail.esta_no_escopo(
            [{"role": "user", "content": req.input}], settings.model_alias
        )
        return {
            "flagged": not no_escopo,
            "mensagem": "" if no_escopo else RECUSA_ESCOPO,
        }

    @app.get("/v1/models", dependencies=[Depends(verificar_api_key)])
    async def listar_modelos() -> dict[str, Any]:
        return {
            "object": "list",
            "data": [{"id": settings.model_alias, "object": "model", "owned_by": "chat_ram"}],
        }

    @app.post("/v1/chat/completions", dependencies=[Depends(verificar_api_key)])
    async def completions(req: ChatRequest, request: Request) -> Any:
        nome_modelo = req.model or settings.model_alias
        mensagens = [m.model_dump() for m in req.messages]
        meta = req.metadata or {}
        chat_id = request.headers.get("x-conversation-id") or meta.get("chat_id")
        request_id = request.headers.get("x-request-id") or meta.get("message_id")
        for mensagem in mensagens:
            achado = _MARCADOR_CONVERSA.search(str(mensagem.get("content", "")))
            if achado:
                chat_id = chat_id or achado.group(1)
                mensagem["content"] = _MARCADOR_CONVERSA.sub("", str(mensagem["content"])).strip()
        chat_id = chat_id or uuid4().hex
        request_id = request_id or uuid4().hex
        cabecalhos = {"x-conversation-id": str(chat_id)}

        if conversa is not None:
            deltas = conversa.stream(chat_id, request_id, mensagens)
        else:
            deltas = (agente or modelo).stream(mensagens, nome_modelo)

        if req.stream:
            return StreamingResponse(
                _eventos(deltas, nome_modelo),
                media_type="text/event-stream",
                headers=cabecalhos,
            )

        try:
            texto = "".join([delta async for delta in deltas])
        except Exception as exc:  # noqa: BLE001
            return JSONResponse(
                status_code=502,
                content={
                    "error": {
                        "message": f"falha no proxy: {exc}",
                        "type": "upstream_error",
                    }
                },
            )
        return JSONResponse(content=_resposta_completa(nome_modelo, texto), headers=cabecalhos)

    return app


async def _eventos(deltas: AsyncIterator[str], nome_modelo: str) -> AsyncIterator[str]:
    id_ = f"chatcmpl-{uuid4().hex}"
    criado = int(time.time())
    yield _sse(_chunk(id_, criado, nome_modelo, delta={"role": "assistant", "content": ""}))
    try:
        async for delta in deltas:
            yield _sse(_chunk(id_, criado, nome_modelo, delta={"content": delta}))
    except Exception as exc:  # noqa: BLE001
        _logger.exception("falha no stream do proxy")
        yield _sse({"error": {"message": f"falha no proxy: {exc}", "type": "upstream_error"}})
    else:
        yield _sse(_chunk(id_, criado, nome_modelo, delta={}, finish_reason="stop"))
    yield "data: [DONE]\n\n"


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _chunk(
    id_: str,
    criado: int,
    nome_modelo: str,
    delta: dict[str, str],
    finish_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "id": id_,
        "object": "chat.completion.chunk",
        "created": criado,
        "model": nome_modelo,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }


def _resposta_completa(nome_modelo: str, texto: str) -> dict[str, Any]:
    return {
        "id": f"chatcmpl-{uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": nome_modelo,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": texto},
                "finish_reason": "stop",
            }
        ],
    }
