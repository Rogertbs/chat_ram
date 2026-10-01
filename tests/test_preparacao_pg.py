"""Integração com o PostgreSQL 18 real: índices, idempotência e leitura OTRS.

Pulado automaticamente quando a cópia fixa não está acessível.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import psycopg
import pytest

from chat_ram.preparacao.dominio import ConfiguracaoPreparacao, Trecho
from chat_ram.preparacao.historico import PostgresHistorico
from chat_ram.preparacao.repositorio import PostgresTrechos

DATA = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)


def _config(modelo: str = "teste-emb", dimensao: int = 3) -> ConfiguracaoPreparacao:
    return ConfiguracaoPreparacao(modelo_embeddings=modelo, dimensao=dimensao)


def _trecho(
    article_id: int,
    content: str,
    embedding: list[float],
    *,
    posicao: int = 0,
    fila: str = "Nivel 1",
) -> Trecho:
    return Trecho(
        tn="2025010100001",
        ticket_id=1000 + article_id,
        article_id=article_id,
        fila=fila,
        data=DATA,
        visivel_cliente=True,
        posicao=posicao,
        versao=1,
        modelo_embeddings="teste-emb",
        dimensao=len(embedding),
        content=content,
        embedding=tuple(embedding),
    )


@pytest.fixture
def repositorio(conexao_pg18: psycopg.Connection[object]) -> Iterator[PostgresTrechos]:
    schema = f"rag_teste_{uuid4().hex[:8]}"
    repo = PostgresTrechos(conexao_pg18, schema=schema)
    try:
        yield repo
    finally:
        conexao_pg18.rollback()
        with conexao_pg18.cursor() as cursor:
            cursor.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        conexao_pg18.commit()


def test_estrutura_idempotente_e_buscas_retornam_fontes(
    repositorio: PostgresTrechos,
) -> None:
    config = _config()
    repositorio.garantir_estrutura(config)
    repositorio.garantir_estrutura(config)
    repositorio.registrar_modelo(config)
    repositorio.salvar(
        [
            _trecho(1, "falha ao conectar na vpn corporativa", [1.0, 0.0, 0.0]),
            _trecho(2, "erro na impressora do setor", [0.0, 1.0, 0.0]),
        ]
    )

    lexicais = repositorio.buscar_lexical("vpn", limite=5)
    vetoriais = repositorio.buscar_vetorial([0.9, 0.1, 0.0], limite=5)

    assert lexicais[0].article_id == 1
    assert lexicais[0].tn == "2025010100001"
    assert lexicais[0].fila == "Nivel 1"
    assert vetoriais[0].article_id == 1
    assert repositorio.cobertura_por_fila() == {"Nivel 1": 2}


def test_filtro_de_fila_restinge_as_duas_buscas(repositorio: PostgresTrechos) -> None:
    config = _config()
    repositorio.garantir_estrutura(config)
    repositorio.registrar_modelo(config)
    repositorio.salvar(
        [
            _trecho(1, "vpn indisponivel", [1.0, 0.0, 0.0], fila="Nivel 1"),
            _trecho(2, "vpn lenta no datacenter", [0.9, 0.1, 0.0], fila="Infraestrutura"),
        ]
    )

    lexicais = repositorio.buscar_lexical("vpn", filas=["Infraestrutura"])
    vetoriais = repositorio.buscar_vetorial([1.0, 0.0, 0.0], filas=["Infraestrutura"])

    assert [r.article_id for r in lexicais] == [2]
    assert [r.article_id for r in vetoriais] == [2]


def test_salvar_de_novo_nao_duplica(repositorio: PostgresTrechos) -> None:
    config = _config()
    repositorio.garantir_estrutura(config)
    repositorio.registrar_modelo(config)

    repositorio.salvar([_trecho(1, "texto antigo", [1.0, 0.0, 0.0])])
    repositorio.salvar([_trecho(1, "texto atualizado", [0.0, 1.0, 0.0])])

    assert repositorio.artigos_processados(versao=1, modelo="teste-emb") == {1}
    assert repositorio.cobertura_por_fila() == {"Nivel 1": 1}
    assert repositorio.buscar_lexical("atualizado")[0].content == "texto atualizado"


def test_salvar_substitui_trechos_quando_o_artigo_encurta(
    repositorio: PostgresTrechos,
) -> None:
    config = _config()
    repositorio.garantir_estrutura(config)
    repositorio.registrar_modelo(config)

    repositorio.salvar(
        [
            _trecho(1, "parte um", [1.0, 0.0, 0.0], posicao=0),
            _trecho(1, "parte dois", [0.9, 0.1, 0.0], posicao=1),
            _trecho(1, "parte três", [0.8, 0.2, 0.0], posicao=2),
        ]
    )
    repositorio.salvar([_trecho(1, "parte única", [1.0, 0.0, 0.0], posicao=0)])

    assert repositorio.cobertura_por_fila() == {"Nivel 1": 1}
    assert [r.content for r in repositorio.buscar_lexical("parte")] == ["parte única"]


def test_modelo_ou_dimensao_diferente_e_recusado(repositorio: PostgresTrechos) -> None:
    repositorio.garantir_estrutura(_config())
    repositorio.registrar_modelo(_config())

    with pytest.raises(ValueError, match="incompat"):
        repositorio.registrar_modelo(_config(modelo="outro-emb"))
    with pytest.raises(ValueError, match="incompat"):
        repositorio.registrar_modelo(_config(dimensao=4))


def test_le_artigos_da_copia_fixa(conexao_pg18: psycopg.Connection[object]) -> None:
    fonte = PostgresHistorico(conexao_pg18)

    artigos = list(fonte.artigos(limite=5))

    assert len(artigos) == 5
    assert all(artigo.tn for artigo in artigos)
    assert all(artigo.fila for artigo in artigos)
    assert all(artigo.article_id > 0 for artigo in artigos)
