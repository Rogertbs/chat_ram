from datetime import UTC, datetime

from chat_ram.conhecimento.busca import buscar_casos, resolver_filas
from chat_ram.preparacao.dominio import ResultadoBusca

DATA = datetime(2026, 1, 1, tzinfo=UTC)


def item(article_id: int, *, tn: str = "1", posicao: int = 0) -> ResultadoBusca:
    return ResultadoBusca(
        tn=tn,
        ticket_id=1,
        article_id=article_id,
        fila="Nivel 1",
        data=DATA,
        visivel_cliente=True,
        posicao=posicao,
        content=f"conteudo {article_id}",
        score=0.0,
    )


class EmbeddingsFake:
    def embed(self, textos: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in textos]


class FonteFake:
    def __init__(
        self,
        lexicais: list[ResultadoBusca],
        vetoriais: list[ResultadoBusca],
        similaridades: dict[tuple[str, int, int], float] | None = None,
    ) -> None:
        self._lexicais = lexicais
        self._vetoriais = vetoriais
        self._sim = similaridades or {}
        self.filas_recebidas: list[tuple[str, list[str] | None]] = []

    def buscar_lexical(
        self, consulta: str, limite: int = 50, filas: list[str] | None = None
    ) -> list[ResultadoBusca]:
        self.filas_recebidas.append(("lex", filas))
        return self._lexicais

    def buscar_vetorial(
        self, embedding: list[float], limite: int = 50, filas: list[str] | None = None
    ) -> list[ResultadoBusca]:
        self.filas_recebidas.append(("vet", filas))
        return self._vetoriais

    def similaridades(
        self, embedding: list[float], chaves: list[tuple[str, int, int]]
    ) -> dict[tuple[str, int, int], float]:
        return {chave: self._sim.get(chave, 0.9) for chave in chaves}


def test_funde_lexical_e_vetorial_por_rrf() -> None:
    fonte = FonteFake([item(1), item(2)], [item(2), item(3)])

    resultado = buscar_casos(fonte, EmbeddingsFake(), "vpn cai")

    assert [caso.article_id for caso in resultado.casos] == [2, 1, 3]
    assert resultado.alcance_suficiente is True


def test_desempate_por_similaridade_de_cosseno() -> None:
    fonte = FonteFake(
        [item(1)],
        [item(2)],
        similaridades={("1", 1, 0): 0.6, ("1", 2, 0): 0.95},
    )

    resultado = buscar_casos(fonte, EmbeddingsFake(), "eco")

    assert [caso.article_id for caso in resultado.casos] == [2, 1]


def test_threshold_remove_matches_fracos() -> None:
    fonte = FonteFake([item(1)], [], similaridades={("1", 1, 0): 0.3})

    resultado = buscar_casos(fonte, EmbeddingsFake(), "algo")

    assert resultado.casos == ()
    assert resultado.alcance_suficiente is False
    assert resultado.mensagem is not None


def test_filtro_de_fila_e_aplicado_as_duas_buscas() -> None:
    fonte = FonteFake([item(1)], [item(1)])

    resultado = buscar_casos(fonte, EmbeddingsFake(), "vpn", filas=["Nivel 1"])

    assert fonte.filas_recebidas == [("lex", ["Nivel 1"]), ("vet", ["Nivel 1"])]
    assert resultado.filas_aplicadas == ("Nivel 1",)


def test_resolver_filas_exato() -> None:
    assert resolver_filas(["Nivel 1", "Nivel 2"], "nivel 1").candidatos == ("Nivel 1",)


def test_resolver_filas_ambiguo_pede_esclarecimento() -> None:
    resultado = resolver_filas(["Nivel 1", "Nivel 2", "Nivel 3"], "nivel")

    assert resultado.ambiguo is True
    assert set(resultado.candidatos) == {"Nivel 1", "Nivel 2", "Nivel 3"}


def test_resolver_filas_sem_correspondencia() -> None:
    assert resolver_filas(["Nivel 1"], "financeiro").candidatos == ()
