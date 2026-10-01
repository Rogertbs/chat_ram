"""Adapter de embeddings pelo proxy LiteLLM (contrato OpenAI /v1/embeddings)."""

from typing import Protocol

import httpx


class Embeddings(Protocol):
    """Produz vetores para textos, na mesma ordem da entrada."""

    def embed(self, textos: list[str]) -> list[list[float]]:
        """Devolve um vetor por texto de entrada."""
        ...


class LiteLLMEmbeddings:
    """Consome /v1/embeddings do LiteLLM, em lotes, validando a dimensão."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        modelo: str,
        dimensao: int,
        lote: int = 64,
        timeout: float = 120.0,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/v1/embeddings"
        self._api_key = api_key
        self._modelo = modelo
        self._dimensao = dimensao
        self._lote = lote
        self._timeout = timeout

    def embed(self, textos: list[str]) -> list[list[float]]:
        resultado: list[list[float]] = []
        with httpx.Client(timeout=self._timeout) as cliente:
            for inicio in range(0, len(textos), self._lote):
                lote = textos[inicio : inicio + self._lote]
                resultado.extend(self._embed_lote(cliente, lote))
        return resultado

    def _embed_lote(self, cliente: httpx.Client, textos: list[str]) -> list[list[float]]:
        resposta = cliente.post(
            self._url,
            json={"model": self._modelo, "input": textos},
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        resposta.raise_for_status()
        itens = sorted(resposta.json()["data"], key=lambda item: item["index"])
        vetores = [item["embedding"] for item in itens]
        if len(vetores) != len(textos):
            raise ValueError(
                f"quantidade de embeddings ({len(vetores)}) difere da de textos ({len(textos)})"
            )
        for vetor in vetores:
            if len(vetor) != self._dimensao:
                raise ValueError(
                    f"dimensão do embedding ({len(vetor)}) difere da esperada ({self._dimensao})"
                )
        return vetores
