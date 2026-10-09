"""
title: Guardrail de Escopo (chat_ram)
description: Bloqueia mensagens fora do escopo (helpdesk/OTRS) consultando o backend chat_ram.
required_open_webui_version: 0.9.0
version: 0.1.0
"""

import aiohttp
from pydantic import BaseModel, Field


class Filter:
    class Valves(BaseModel):
        base_url: str = Field(
            default="__CHAT_RAM_BASE_URL__", description="URL do backend chat_ram"
        )
        api_key: str = Field(default="__CHAT_RAM_API_KEY__", description="CHAT_RAM_API_KEY")

    def __init__(self):
        self.valves = self.Valves()

    async def inlet(self, body: dict, **kwargs) -> dict:
        # Encaminha o id da conversa ao backend (a Open WebUI não envia metadata).
        chat_id = (body.get("metadata") or {}).get("chat_id") or body.get("chat_id")
        if chat_id:
            for mensagem in reversed(body.get("messages", [])):
                if mensagem.get("role") == "user":
                    conteudo = mensagem.get("content", "")
                    if isinstance(conteudo, str) and "[[chat_ram_id:" not in conteudo:
                        mensagem["content"] = f"{conteudo}\n[[chat_ram_id:{chat_id}]]"
                    break

        texto = ""
        for mensagem in reversed(body.get("messages", [])):
            if mensagem.get("role") == "user":
                conteudo = mensagem.get("content", "")
                texto = conteudo if isinstance(conteudo, str) else ""
                break
        if not texto.strip():
            return body

        url = self.valves.base_url.rstrip("/") + "/guardrail"
        headers = {"Authorization": f"Bearer {self.valves.api_key}"}
        try:
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    url,
                    json={"input": texto},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resposta,
            ):
                if resposta.status != 200:
                    return body
                dados = await resposta.json()
        except Exception:
            return body

        if dados.get("flagged"):
            raise Exception(
                dados.get("mensagem")
                or "Fora do escopo: só ajudo com problemas técnicos de helpdesk e OTRS."
            )
        return body
