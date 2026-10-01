import pytest

from chat_ram.config import Settings


def test_carrega_configuracao_do_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_BASE_URL", "http://localhost:4000")
    monkeypatch.setenv("LITELLM_API_KEY", "sk-teste")
    monkeypatch.setenv("MODEL_ALIAS", "qwen-local")

    cfg = Settings()  # type: ignore[call-arg]

    assert cfg.litellm_base_url == "http://localhost:4000"
    assert cfg.litellm_api_key == "sk-teste"
    assert cfg.model_alias == "qwen-local"
