# 01: Chat streaming de ponta a ponta

**What to build:** O esqueleto andante do projeto (estrutura, dependências, configuração e `.env`) mais a API compatível com o formato OpenAI (`/v1/chat/completions`) que encaminha ao proxy LiteLLM. O analista conversa na Open WebUI e vê a resposta chegar progressivamente (streaming), ainda sem ferramentas.

**Blocked by:** None (can start immediately)

**Status:** needs-info

- [ ] A Open WebUI, apontada para a API deste servidor, envia uma mensagem e recebe a resposta completa em streaming
- [x] URL/base e alias do modelo vêm do `.env`; nenhum segredo no código
- [x] Falha do proxy é reportada sem travar a conversa
- [ ] Requisição real registrada como evidência (Etapa 1 do MVP)

## Comments

- Implementado e testado (commit `c4b39fd`): API OpenAI-compatible com `POST /v1/chat/completions` (stream e não-stream), `GET /v1/models`, config por `.env` e `.env.example`. Testes com backend fake (8 passando), ruff e mypy verdes.
- Pendente: evidência real (Open WebUI → API → LiteLLM) — **bloqueada até termos o IP/base, o alias do modelo e a chave** do proxy no `.env`. Por isso `needs-info`.
