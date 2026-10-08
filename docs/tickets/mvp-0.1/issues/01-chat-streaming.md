# 01: Chat streaming de ponta a ponta

**What to build:** O esqueleto andante do projeto (estrutura, dependências, configuração e `.env`) mais a API compatível com o formato OpenAI (`/v1/chat/completions`) que encaminha ao proxy LiteLLM. O analista conversa na Open WebUI e vê a resposta chegar progressivamente (streaming), ainda sem ferramentas.

**Blocked by:** None (can start immediately)

**Status:** ready-for-human

- [ ] A Open WebUI, apontada para a API deste servidor, envia uma mensagem e recebe a resposta completa em streaming
- [x] URL/base e alias do modelo vêm do `.env`; nenhum segredo no código
- [x] Falha do proxy é reportada sem travar a conversa
- [x] Requisição real registrada como evidência (Etapa 1 do MVP)

## Comments

- Implementado e testado (commit `c4b39fd`): API OpenAI-compatible com `POST /v1/chat/completions` (stream e não-stream), `GET /v1/models`, config por `.env` e `.env.example`. Testes com backend fake (8 passando), ruff e mypy verdes.
- Evidência real (proxy OpenRouter free, modelo `nvidia/nemotron-3-super-120b-a12b:free`) via ASGI da própria API:
  - `GET /v1/models` → 200, `['nvidia/nemotron-3-super-120b-a12b:free']`
  - `POST /v1/chat/completions` (sem stream) → 200, conteúdo `"ola mundo"`
  - `POST /v1/chat/completions` (`stream: true`) → 200, `text/event-stream`, deltas SSE concatenando `"ola mundo"`
- Base do proxy no `.env` deve ser **sem `/v1`** (o adapter acrescenta): `LITELLM_BASE_URL=https://openrouter.ai/api`.
- Pendente para aceite humano: apontar a **Open WebUI** real para esta API e conferir o streaming na interface (a API já é OpenAI-compatible, então deve funcionar sem mudança de código). Por isso `ready-for-human`.
