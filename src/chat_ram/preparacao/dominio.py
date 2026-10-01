"""Tipos do domínio da Preparação do histórico."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Artigo:
    """Artigo do OTRS lido da cópia fixa, ainda sem normalização."""

    tn: str
    ticket_id: int
    article_id: int
    fila: str
    data: datetime
    visivel_cliente: bool
    assunto: str
    corpo: str

    def chave(self) -> tuple[int, int]:
        return (self.ticket_id, self.article_id)


@dataclass(frozen=True)
class Trecho:
    """Segmento de um artigo, com fonte e vetor, pronto para gravação."""

    tn: str
    ticket_id: int
    article_id: int
    fila: str
    data: datetime
    visivel_cliente: bool
    posicao: int
    versao: int
    modelo_embeddings: str
    dimensao: int
    content: str
    embedding: tuple[float, ...]


@dataclass(frozen=True)
class ResultadoBusca:
    """Trecho retornado por uma busca, com o escore do índice consultado."""

    tn: str
    ticket_id: int
    article_id: int
    fila: str
    data: datetime
    visivel_cliente: bool
    posicao: int
    content: str
    score: float


@dataclass(frozen=True)
class ConfiguracaoPreparacao:
    """Parâmetros de uma execução da Preparação."""

    modelo_embeddings: str
    dimensao: int = 1024
    versao: int = 1
    tamanho_max: int = 2000
    sobreposicao: int = 200
    lote_embeddings: int = 64
    retomar: bool = True


@dataclass
class RelatorioPreparacao:
    """Resultado observável de uma execução da Preparação."""

    modelo_embeddings: str
    dimensao: int
    versao: int
    artigos_lidos: int = 0
    artigos_retomados: int = 0
    artigos_com_texto: int = 0
    trechos_gerados: int = 0
    textos_vazios: list[int] = field(default_factory=list)
    falhas_conversao: list[tuple[int, str]] = field(default_factory=list)
    cobertura_por_fila: dict[str, int] = field(default_factory=dict)
