"""Instala o filtro de guardrail de escopo na Open WebUI via API.

Uso (a partir da raiz do projeto, com a UI no ar):
    .venv/bin/python openwebui/instalar_filtro.py
"""

from __future__ import annotations

import contextlib
import json
import urllib.request
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

_AQUI = Path(__file__).resolve().parent
_CFG = dotenv_values(_AQUI.parent / ".env")
_BASE = "http://127.0.0.1:3000"
_ID = "guardrail_escopo"


def _post(caminho: str, payload: dict[str, Any], token: str | None = None) -> Any:
    cabecalhos = {"Content-Type": "application/json"}
    if token:
        cabecalhos["Authorization"] = f"Bearer {token}"
    requisicao = urllib.request.Request(
        _BASE + caminho, data=json.dumps(payload).encode(), headers=cabecalhos
    )
    with urllib.request.urlopen(requisicao, timeout=30) as resposta:
        return json.load(resposta)


def _delete(caminho: str, token: str) -> None:
    requisicao = urllib.request.Request(
        _BASE + caminho,
        method="DELETE",
        headers={"Authorization": f"Bearer {token}"},
    )
    with contextlib.suppress(Exception):
        urllib.request.urlopen(requisicao, timeout=30)


def main() -> int:
    email = _CFG.get("WEBUI_ADMIN_EMAIL")
    senha = _CFG.get("WEBUI_ADMIN_PASSWORD")
    chave = _CFG.get("CHAT_RAM_API_KEY", "")
    if not email or not senha:
        raise SystemExit("Defina WEBUI_ADMIN_EMAIL e WEBUI_ADMIN_PASSWORD no .env")

    token = _post("/api/v1/auths/signin", {"email": email, "password": senha})["token"]

    codigo = (_AQUI / "filtro_escopo.py").read_text(encoding="utf-8")
    codigo = codigo.replace("__CHAT_RAM_API_KEY__", chave).replace(
        "__CHAT_RAM_BASE_URL__", "http://app:8000"
    )

    _delete(f"/api/v1/functions/id/{_ID}/delete", token)
    _post(
        "/api/v1/functions/create",
        {
            "id": _ID,
            "name": "Guardrail de Escopo (chat_ram)",
            "meta": {"description": "Bloqueia mensagens fora do escopo", "type": "filter"},
            "content": codigo,
        },
        token,
    )
    _post(f"/api/v1/functions/id/{_ID}/toggle", {}, token)
    _post(f"/api/v1/functions/id/{_ID}/toggle/global", {}, token)
    print(f"Filtro '{_ID}' instalado, ativo e global.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
