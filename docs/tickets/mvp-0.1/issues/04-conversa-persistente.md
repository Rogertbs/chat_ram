# 04: Conversa persistente

**What to build:** A persistência do estado da conversa por `thread_id` — tabela `chat` mais o checkpointer do LangGraph, em schema próprio separado dos dados OTRS. A fila selecionada, o ticket em foco e os esclarecimentos pendentes sobrevivem a fechar e reabrir a interface, e conversas diferentes não compartilham contexto.

**Blocked by:** 01 — Chat streaming de ponta a ponta

**Status:** ready-for-agent

- [ ] Retomar uma conversa após fechar a interface restaura o estado correto
- [ ] Duas conversas simultâneas não vazam contexto entre si
- [ ] O identificador estável de conversa fornecido pela UI é ligado ao `thread_id` e testado
- [ ] Nova tentativa da mesma requisição não duplica mensagens
