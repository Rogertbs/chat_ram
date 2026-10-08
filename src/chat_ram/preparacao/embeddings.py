"""Adapter de embeddings pelo proxy LiteLLM (contrato OpenAI /v1/embeddings)."""

import math
from typing import Protocol

import httpx


class Embeddings(Protocol):
    """Produz vetores para textos, na mesma ordem da entrada."""

    def embed(self, textos: list[str]) -> list[list[float]]:
        """Devolve um vetor por texto de entrada."""
        ...


class LiteLLMEmbeddings:
    """Consome /v1/embeddings do LiteLLM, em lotes, validando a dimensão.

    Com `truncar_para`, aplica truncamento MRL local (corta e renormaliza em L2),
    útil quando o modelo devolve mais dimensões do que a coluna vetorial.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        modelo: str,
        dimensao: int,
        lote: int = 64,
        timeout: float = 120.0,
        truncar_para: int | None = None,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/v1/embeddings"
        self._api_key = api_key
        self._modelo = modelo
        self._dimensao = dimensao
        self._lote = lote
        self._timeout = timeout
        self._truncar_para = truncar_para

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
        if self._truncar_para is not None:
            vetores = [_truncar_normalizar(vetor, self._truncar_para) for vetor in vetores]
        for vetor in vetores:
            if len(vetor) != self._dimensao:
                raise ValueError(
                    f"dimensão do embedding ({len(vetor)}) difere da esperada ({self._dimensao})"
                )
        return vetores


def _truncar_normalizar(vetor: list[float], alvo: int) -> list[float]:
    """Corta o vetor para as primeiras `alvo` dimensões e renormaliza em L2."""
    if len(vetor) < alvo:
        raise ValueError(f"vetor de {len(vetor)} dimensões é menor que o alvo {alvo}")
    truncado = [float(valor) for valor in vetor[:alvo]]
    norma = math.sqrt(sum(valor * valor for valor in truncado))
    if norma == 0.0:
        return truncado
    return [valor / norma for valor in truncado]
