from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from chat_ram.preparacao.dominio import (
    Artigo,
    ConfiguracaoPreparacao,
    RelatorioPreparacao,
    Trecho,
)
from chat_ram.preparacao.preparador import preparar
from chat_ram.preparacao.texto import normalizar_artigo

DATA = datetime(2025, 1, 1, tzinfo=UTC)


def artigo(
    article_id: int,
    assunto: str = "Assunto",
    corpo: str = "Corpo do artigo",
    *,
    tn: str = "2025010100001",
    fila: str = "Nivel 1",
) -> Artigo:
    return Artigo(
        tn=tn,
        ticket_id=100 + article_id,
        article_id=article_id,
        fila=fila,
        data=DATA,
        visivel_cliente=True,
        assunto=assunto,
        corpo=corpo,
    )


def config(**kwargs: object) -> ConfiguracaoPreparacao:
    base: dict[str, object] = {"modelo_embeddings": "qwen-emb", "dimensao": 3}
    base.update(kwargs)
    return ConfiguracaoPreparacao(**base)  # type: ignore[arg-type]


class FonteFake:
    def __init__(self, artigos: list[Artigo]) -> None:
        self._artigos = artigos

    def artigos(self, limite: int | None = None) -> Iterator[Artigo]:
        return iter(self._artigos if limite is None else self._artigos[:limite])


class EmbeddingsFake:
    def __init__(self) -> None:
        self.chamadas: list[list[str]] = []

    def embed(self, textos: list[str]) -> list[list[float]]:
        self.chamadas.append(list(textos))
        return [[float(len(texto)), 0.0, 1.0] for texto in textos]


class RepoFake:
    def __init__(
        self,
        ja_processados: set[int] | None = None,
        cobertura: dict[str, int] | None = None,
        recusa_modelo: str | None = None,
    ) -> None:
        self._ja = ja_processados or set()
        self._cobertura = cobertura or {}
        self._recusa_modelo = recusa_modelo
        self.trechos: list[Trecho] = []
        self.estrutura_garantida = 0
        self.modelo_registrado: str | None = None

    def garantir_estrutura(self, cfg: ConfiguracaoPreparacao) -> None:
        self.estrutura_garantida += 1

    def registrar_modelo(self, cfg: ConfiguracaoPreparacao) -> None:
        if self._recusa_modelo == cfg.modelo_embeddings:
            raise ValueError("modelo incompatível com os vetores já gravados")
        self.modelo_registrado = cfg.modelo_embeddings

    def artigos_processados(self, versao: int, modelo: str) -> set[int]:
        return self._ja

    def salvar(self, trechos: list[Trecho]) -> None:
        self.trechos.extend(trechos)

    def cobertura_por_fila(self) -> dict[str, int]:
        return self._cobertura


def test_gera_um_trecho_por_artigo_curto() -> None:
    repo = RepoFake()

    relatorio = preparar(
        FonteFake([artigo(1, "Falha de rede", "A VPN não conecta")]),
        EmbeddingsFake(),
        repo,
        config(),
    )

    assert relatorio.artigos_lidos == 1
    assert relatorio.artigos_com_texto == 1
    assert relatorio.trechos_gerados == 1
    assert len(repo.trechos) == 1
    trecho = repo.trechos[0]
    assert trecho.content == "Falha de rede\n\nA VPN não conecta"
    assert (trecho.posicao, trecho.versao, trecho.modelo_embeddings, trecho.dimensao) == (
        0,
        1,
        "qwen-emb",
        3,
    )
    assert trecho.embedding == (float(len(trecho.content)), 0.0, 1.0)
    assert (trecho.tn, trecho.fila, trecho.visivel_cliente) == ("2025010100001", "Nivel 1", True)


def test_divide_artigo_longo_com_sobreposicao() -> None:
    repo = RepoFake()

    relatorio = preparar(
        FonteFake([artigo(1, assunto="", corpo="a" * 2500)]),
        EmbeddingsFake(),
        repo,
        config(),
    )

    assert relatorio.trechos_gerados == 2
    assert [t.posicao for t in repo.trechos] == [0, 1]
    assert [len(t.content) for t in repo.trechos] == [2000, 700]


def test_conta_textos_vazios_sem_gravar() -> None:
    repo = RepoFake()

    relatorio = preparar(
        FonteFake([artigo(7, assunto="", corpo="   ")]),
        EmbeddingsFake(),
        repo,
        config(),
    )

    assert relatorio.textos_vazios == [7]
    assert relatorio.trechos_gerados == 0
    assert repo.trechos == []


def test_falha_de_conversao_e_registrada_e_nao_aborta() -> None:
    def normalizar(assunto: str, corpo: str) -> str:
        if "boom" in corpo:
            raise RuntimeError("html quebrado")
        return normalizar_artigo(assunto, corpo)

    repo = RepoFake()

    relatorio = preparar(
        FonteFake([artigo(1, corpo="boom"), artigo(2, corpo="ok")]),
        EmbeddingsFake(),
        repo,
        config(),
        normalizar=normalizar,
    )

    assert relatorio.falhas_conversao == [(1, "html quebrado")]
    assert [t.article_id for t in repo.trechos] == [2]


def test_retomada_nao_reprocessa_artigos_ja_gravados() -> None:
    repo = RepoFake(ja_processados={1})

    relatorio = preparar(
        FonteFake([artigo(1), artigo(2)]),
        EmbeddingsFake(),
        repo,
        config(),
    )

    assert relatorio.artigos_lidos == 2
    assert relatorio.artigos_retomados == 1
    assert [t.article_id for t in repo.trechos] == [2]


def test_modelo_incompativel_aborta_antes_de_gravar() -> None:
    repo = RepoFake(recusa_modelo="qwen-emb")

    with pytest.raises(ValueError, match="incompat"):
        preparar(FonteFake([artigo(1)]), EmbeddingsFake(), repo, config())

    assert repo.trechos == []


def test_relatorio_traz_cobertura_por_fila() -> None:
    repo = RepoFake(cobertura={"Nivel 1": 5, "Infraestrutura": 2})

    relatorio: RelatorioPreparacao = preparar(
        FonteFake([artigo(1)]), EmbeddingsFake(), repo, config()
    )

    assert relatorio.cobertura_por_fila == {"Nivel 1": 5, "Infraestrutura": 2}


def test_limite_restringe_os_artigos_lidos() -> None:
    repo = RepoFake()

    relatorio = preparar(
        FonteFake([artigo(1), artigo(2), artigo(3)]),
        EmbeddingsFake(),
        repo,
        config(),
        limite=2,
    )

    assert relatorio.artigos_lidos == 2
    assert [t.article_id for t in repo.trechos] == [1, 2]


def test_embeddings_sao_gerados_em_lote() -> None:
    embeddings = EmbeddingsFake()
    repo = RepoFake()

    preparar(FonteFake([artigo(1), artigo(2)]), embeddings, repo, config(lote_embeddings=64))

    assert len(embeddings.chamadas) == 1
    assert len(embeddings.chamadas[0]) == 2
