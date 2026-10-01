# 01: Chat streaming de ponta a ponta

**What to build:** O esqueleto andante do projeto (estrutura, dependências, configuração e `.env`) mais a API compatível com o formato OpenAI (`/v1/chat/completions`) que encaminha ao proxy LiteLLM. O analista conversa na Open WebUI e vê a resposta chegar progressivamente (streaming), ainda sem ferramentas.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] A Open WebUI, apontada para a API deste servidor, envia uma mensagem e recebe a resposta completa em streaming
- [ ] URL/base e alias do modelo vêm do `.env`; nenhum segredo no código
- [ ] Falha do proxy é reportada sem travar a conversa
- [ ] Requisição real registrada como evidência (Etapa 1 do MVP)
