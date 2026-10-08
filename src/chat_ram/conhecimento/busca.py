"""Busca de casos semelhantes (híbrida, fundida por RRF) e resolução de filas."""

from typing import Protocol

from ..preparacao.dominio import ResultadoBusca
from .dominio import Caso, ResultadoCasos, ResultadoFilas

K_RRF = 60
CANDIDATOS = 50
FINAL = 8
THRESHOLD_COSSENO = 0.5

Chave = tuple[str, int, int]


class FonteBusca(Protocol):
    """Índices de trechos consultáveis (lexical e vetorial)."""

    def buscar_lexical(
        self, consulta: str, limite: int = CANDIDATOS, filas: list[str] | None = None
    ) -> list[ResultadoBusca]: ...

    def buscar_vetorial(
        self, embedding: list[float], limite: int = CANDIDATOS, filas: list[str] | None = None
    ) -> list[ResultadoBusca]: ...

    def similaridades(self, embedding: list[float], chaves: list[Chave]) -> dict[Chave, float]: ...


class Embeddings(Protocol):
    """Gera o vetor da pergunta (mesmo modelo dos trechos)."""

    def embed(self, textos: list[str]) -> list[list[float]]: ...


class FonteFilas(Protocol):
    """Lista as filas existentes no OTRS."""

    def listar_filas(self) -> list[str]: ...


def buscar_casos(
    fonte: FonteBusca,
    embeddings: Embeddings,
    pergunta: str,
    filas: list[str] | None = None,
    *,
    k: int = K_RRF,
    candidatos: int = CANDIDATOS,
    final: int = FINAL,
    threshold: float = THRESHOLD_COSSENO,
) -> ResultadoCasos:
    """Funde BM25 e vetor por RRF, aplica o threshold de cosseno e ordena."""
    vetor = embeddings.embed([pergunta])[0]
    lexicais = fonte.buscar_lexical(pergunta, candidatos, filas)
    vetoriais = fonte.buscar_vetorial(vetor, candidatos, filas)

    scores: dict[Chave, float] = {}
    itens: dict[Chave, ResultadoBusca] = {}
    for lista in (lexicais, vetoriais):
        for posicao, item in enumerate(lista, start=1):
            chave = _chave(item)
            scores[chave] = scores.get(chave, 0.0) + 1.0 / (k + posicao)
            itens.setdefault(chave, item)

    similaridades = fonte.similaridades(vetor, list(itens))
    aprovados = [
        (chave, itens[chave], scores[chave], similaridades.get(chave, -1.0))
        for chave in itens
        if similaridades.get(chave, -1.0) >= threshold
    ]
    aprovados.sort(key=lambda item: (-item[2], -item[3], item[0][0], item[0][1], item[0][2]))

    casos = tuple(
        _caso(item, score, similaridade) for _, item, score, similaridade in aprovados[:final]
    )
    return ResultadoCasos(
        casos=casos,
        alcance_suficiente=bool(casos),
        filas_aplicadas=tuple(filas) if filas else None,
        mensagem=None
        if casos
        else "sem resultados suficientes no alcance da busca; não preencher com matches fracos",
    )


def resolver_filas(filas: list[str], texto: str) -> ResultadoFilas:
    """Casa o texto informado com as filas; devolve candidatos e ambiguidade."""
    alvo = texto.strip().casefold()
    if not alvo:
        return ResultadoFilas((), False)
    exatos = tuple(fila for fila in filas if fila.casefold() == alvo)
    if exatos:
        return ResultadoFilas(exatos, False)
    parciais = tuple(fila for fila in filas if alvo in fila.casefold() or fila.casefold() in alvo)
    return ResultadoFilas(parciais, ambiguo=len(parciais) > 1)


def _chave(item: ResultadoBusca) -> Chave:
    return (item.tn, item.article_id, item.posicao)


def _caso(item: ResultadoBusca, score: float, similaridade: float) -> Caso:
    return Caso(
        tn=item.tn,
        ticket_id=item.ticket_id,
        article_id=item.article_id,
        fila=item.fila,
        data=item.data,
        visivel_cliente=item.visivel_cliente,
        posicao=item.posicao,
        content=item.content,
        similaridade=similaridade,
        score=score,
    )
