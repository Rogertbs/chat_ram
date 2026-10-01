"""Orquestra a Preparação do histórico em lote."""

from collections.abc import Callable

from .dominio import Artigo, ConfiguracaoPreparacao, RelatorioPreparacao, Trecho
from .embeddings import Embeddings
from .historico import FonteHistorico
from .repositorio import RepositorioPreparacao
from .texto import normalizar_artigo, segmentar

Normalizador = Callable[[str, str], str]


def preparar(
    fonte: FonteHistorico,
    embeddings: Embeddings,
    repositorio: RepositorioPreparacao,
    config: ConfiguracaoPreparacao,
    *,
    normalizar: Normalizador = normalizar_artigo,
    limite: int | None = None,
) -> RelatorioPreparacao:
    """Lê os artigos, segmenta, gera embeddings e grava, emitindo um relatório."""
    repositorio.garantir_estrutura(config)
    repositorio.registrar_modelo(config)

    retomados = (
        repositorio.artigos_processados(config.versao, config.modelo_embeddings)
        if config.retomar
        else set()
    )
    relatorio = RelatorioPreparacao(
        modelo_embeddings=config.modelo_embeddings,
        dimensao=config.dimensao,
        versao=config.versao,
    )
    buffer: list[tuple[Artigo, list[str]]] = []
    pendentes = 0

    def gravar_lote() -> None:
        nonlocal pendentes
        if not buffer:
            return
        textos = [texto for _, textos_artigo in buffer for texto in textos_artigo]
        vetores = embeddings.embed(textos)
        trechos = _montar_trechos(buffer, vetores, config)
        repositorio.salvar(trechos)
        relatorio.trechos_gerados += len(trechos)
        buffer.clear()
        pendentes = 0

    for artigo in fonte.artigos(limite):
        relatorio.artigos_lidos += 1
        if artigo.article_id in retomados:
            relatorio.artigos_retomados += 1
            continue
        try:
            texto = normalizar(artigo.assunto, artigo.corpo)
        except Exception as exc:  # noqa: BLE001
            relatorio.falhas_conversao.append((artigo.article_id, str(exc)))
            continue
        if not texto.strip():
            relatorio.textos_vazios.append(artigo.article_id)
            continue
        textos = segmentar(texto, config.tamanho_max, config.sobreposicao)
        buffer.append((artigo, textos))
        pendentes += len(textos)
        relatorio.artigos_com_texto += 1
        if pendentes >= config.lote_embeddings:
            gravar_lote()

    gravar_lote()
    relatorio.cobertura_por_fila = repositorio.cobertura_por_fila()
    return relatorio


def _montar_trechos(
    buffer: list[tuple[Artigo, list[str]]],
    vetores: list[list[float]],
    config: ConfiguracaoPreparacao,
) -> list[Trecho]:
    trechos: list[Trecho] = []
    cursor = 0
    for artigo, textos in buffer:
        for posicao, conteudo in enumerate(textos):
            trechos.append(
                Trecho(
                    tn=artigo.tn,
                    ticket_id=artigo.ticket_id,
                    article_id=artigo.article_id,
                    fila=artigo.fila,
                    data=artigo.data,
                    visivel_cliente=artigo.visivel_cliente,
                    posicao=posicao,
                    versao=config.versao,
                    modelo_embeddings=config.modelo_embeddings,
                    dimensao=config.dimensao,
                    content=conteudo,
                    embedding=tuple(vetores[cursor]),
                )
            )
            cursor += 1
    return trechos
