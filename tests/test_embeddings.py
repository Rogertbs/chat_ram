import httpx
import pytest
import respx

from chat_ram.preparacao.embeddings import LiteLLMEmbeddings


def _resposta(*vetores: list[float]) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "object": "list",
            "data": [
                {"object": "embedding", "index": i, "embedding": v} for i, v in enumerate(vetores)
            ],
        },
    )


def test_gera_embeddings_na_ordem_dos_textos() -> None:
    embeddings = LiteLLMEmbeddings("http://proxy", "sk", modelo="emb", dimensao=3, lote=8)

    with respx.mock(base_url="http://proxy") as mock:
        mock.post("/v1/embeddings").mock(return_value=_resposta([1.0, 0.0, 0.0], [0.0, 1.0, 0.0]))
        resultado = embeddings.embed(["primeiro", "segundo"])

    assert resultado == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]


def test_envia_modelo_e_textos_no_payload() -> None:
    embeddings = LiteLLMEmbeddings("http://proxy", "sk", modelo="qwen-emb", dimensao=3)

    with respx.mock(base_url="http://proxy") as mock:
        rota = mock.post("/v1/embeddings").mock(return_value=_resposta([1.0, 2.0, 3.0]))
        embeddings.embed(["olá"])
        enviado = rota.calls[0].request

    assert enviado.headers["authorization"] == "Bearer sk"
    corpo = httpx.Response(200, content=enviado.content).json()
    assert corpo["model"] == "qwen-emb"
    assert corpo["input"] == ["olá"]


def test_omite_dimensions_por_padrao() -> None:
    embeddings = LiteLLMEmbeddings("http://proxy", "sk", modelo="emb", dimensao=3)

    with respx.mock(base_url="http://proxy") as mock:
        rota = mock.post("/v1/embeddings").mock(return_value=_resposta([1.0, 2.0, 3.0]))
        embeddings.embed(["olá"])
        corpo = httpx.Response(200, content=rota.calls[0].request.content).json()

    assert "dimensions" not in corpo


def test_envia_dimensions_quando_configurado() -> None:
    embeddings = LiteLLMEmbeddings(
        "http://proxy", "sk", modelo="emb", dimensao=1024, dimensions=1024
    )

    with respx.mock(base_url="http://proxy") as mock:
        rota = mock.post("/v1/embeddings").mock(return_value=_resposta([1.0] * 1024))
        embeddings.embed(["olá"])
        corpo = httpx.Response(200, content=rota.calls[0].request.content).json()

    assert corpo["dimensions"] == 1024


def test_respeita_o_tamanho_do_lote() -> None:
    embeddings = LiteLLMEmbeddings("http://proxy", "sk", modelo="emb", dimensao=1, lote=2)

    with respx.mock(base_url="http://proxy") as mock:
        rota = mock.post("/v1/embeddings").mock(
            side_effect=[
                _resposta([1.0], [2.0]),
                _resposta([3.0]),
            ]
        )
        resultado = embeddings.embed(["a", "b", "c"])

    assert resultado == [[1.0], [2.0], [3.0]]
    assert rota.call_count == 2


def test_dimensao_divergente_e_rejeitada() -> None:
    embeddings = LiteLLMEmbeddings("http://proxy", "sk", modelo="emb", dimensao=1024)

    with respx.mock(base_url="http://proxy") as mock:
        mock.post("/v1/embeddings").mock(return_value=_resposta([1.0, 2.0, 3.0]))
        with pytest.raises(ValueError, match="dimens"):
            embeddings.embed(["texto"])


def test_quantidade_divergente_e_rejeitada() -> None:
    embeddings = LiteLLMEmbeddings("http://proxy", "sk", modelo="emb", dimensao=3)

    with respx.mock(base_url="http://proxy") as mock:
        mock.post("/v1/embeddings").mock(return_value=_resposta([1.0, 0.0, 0.0]))
        with pytest.raises(ValueError, match="quantidade"):
            embeddings.embed(["um", "dois"])
