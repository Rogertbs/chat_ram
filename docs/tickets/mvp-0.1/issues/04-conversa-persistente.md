# 04: Conversa persistente

**What to build:** A persistência do estado da conversa por `thread_id` — tabela `chat` mais o checkpointer do LangGraph, em schema próprio separado dos dados OTRS. A fila selecionada, o ticket em foco e os esclarecimentos pendentes sobrevivem a fechar e reabrir a interface, e conversas diferentes não compartilham contexto.

**Blocked by:** 01 — Chat streaming de ponta a ponta

**Status:** ready-for-human

- [x] Retomar uma conversa após fechar a interface restaura o estado correto
- [x] Duas conversas simultâneas não vazam contexto entre si
- [x] O identificador estável de conversa fornecido pela UI é ligado ao `thread_id` e testado
- [x] Nova tentativa da mesma requisição não duplica mensagens

## Comments

- Módulo **Persistência** (`src/chat_ram/persistencia/`), em schema próprio `conversa` separado do OTRS: `chat` (vínculo `chat_id` ↔ `thread_id`), `mensagem` (histórico por `thread_id`, `UNIQUE (thread_id, request_id, papel)`) e `estado` (fila selecionada, ticket em foco, esclarecimentos). `PostgresConversas` implementa o protocolo; `garantir_estrutura` é idempotente.
- **Conversa** (`conversa.py`): `Conversa.stream(chat_id, request_id, mensagens)` resolve o `thread_id`, restaura o histórico persistido (autoritativo; ignora o histórico reenviado pela UI), grava a mensagem do usuário, responde com o agente e grava a resposta; registra o **ticket em foco** quando a ferramenta `consultar_ticket` encontra um ticket.
- **API**: aceita `X-Conversation-Id` e `X-Request-Id` (gera se faltarem) e devolve `X-Conversation-Id`; sem esses cabeçalhos o comportamento antigo (issue 01) permanece.
- **Decisão registrada no ADR-0006**: persistência em tabelas próprias em vez do checkpointer do LangGraph, porque o agente desta versão é um loop próprio; o `thread_id` segue como chave estável do ADR-0002.
- **Testes** (66 no total): unitários com repositório fake (retomada restaura histórico, isolamento, id estável, retentativa sem duplicação, ticket em foco) e integração com o PostgreSQL 18 (vínculo, idempotência, isolamento, estado). `ruff` e `mypy --strict` verdes.
- **Evidência real** (mock + OpenRouter free): em `chatA`, pedir `2026011600004` gravou `ticket_em_foco=2026011600004` e 2 mensagens; retentativa da mesma requisição manteve 2 mensagens; `chatB` ficou isolado com seu próprio `thread_id` e mensagens.
- Pendente para aceite humano: validar retomada após reiniciar o backend e com a **Open WebUI** encaminhando o id de conversa (pode exigir uma extensão pequena da UI, como prevê a arquitetura). Por isso `ready-for-human`.
