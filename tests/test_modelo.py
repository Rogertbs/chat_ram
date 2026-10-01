import httpx
import pytest
import respx

from chat_ram.modelo import LiteLLMModel

SSE_RESPOSTA = (
    'data: {"choices":[{"delta":{"role":"assistant","content":""}}]}\n\n'
    'data: {"choices":[{"delta":{"content":"Olá"}}]}\n\n'
    'data: {"choices":[{"delta":{"content":" mundo"}}]}\n\n'
    'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
    "data: [DONE]\n\n"
)


async def test_stream_extrai_os_deltas_de_texto() -> None:
    modelo = LiteLLMModel("http://proxy", "sk")

    with respx.mock(base_url="http://proxy") as mock:
        mock.post("/v1/chat/completions").mock(return_value=httpx.Response(200, text=SSE_RESPOSTA))
        deltas: list[str] = [
            delta
            async for delta in modelo.stream([{"role": "user", "content": "oi"}], "qwen-local")
        ]

    assert deltas == ["Olá", " mundo"]


async def test_linha_de_erro_do_proxy_e_reportada() -> None:
    modelo = LiteLLMModel("http://proxy", "sk")

    with respx.mock(base_url="http://proxy") as mock:
        mock.post("/v1/chat/completions").mock(
            return_value=httpx.Response(200, text='data: {"error":{"message":"boom"}}\n\n')
        )
        with pytest.raises(RuntimeError, match="boom"):
            _ = [delta async for delta in modelo.stream([], "qwen-local")]
