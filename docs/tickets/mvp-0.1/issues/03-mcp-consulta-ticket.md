# 03: Servidor MCP e consulta por ticket

**What to build:** O servidor FastMCP com a ferramenta `consultar_ticket(numero, pergunta?)`, conectado ao backend LangGraph como cliente. O agente chama a ferramenta quando o usuário informa um número de ticket e entrega um resumo cronológico (problema, tentativas, solução documentada, situação) com fontes conferíveis, distinguindo ticket não encontrado, fila ambígua e falha técnica.

**Blocked by:** 01 — Chat streaming de ponta a ponta

**Status:** ready-for-human

- [x] Pedir um número de ticket na conversa retorna o resumo cronológico com referências conferíveis
- [x] Número inexistente é reportado como não encontrado — o ticket nunca é inventado
- [x] Ticket extenso é resumido em blocos cronológicos, sinalizando cobertura parcial
- [x] O contrato do proxy (tool calling) foi validado antes de depender dele

## Comments

- Módulo **Conhecimento OTRS** (`src/chat_ram/conhecimento/`): consulta exata por `tn` (nunca por similaridade), artigos em ordem cronológica com `article_id`/data/visibilidade (fonte conferível), desfechos `encontrado` / `nao_encontrado` / `ambiguo` / `falha`, e divisão em blocos cronológicos com `cobertura_parcial` para tickets extensos. Implementação Postgres em `repositorio.py` (tabelas `ticket`, `queue`, `ticket_state`, `article`, `article_data_mime`).
- **Servidor FastMCP** (`conhecimento/mcp.py`) com a ferramenta `consultar_ticket`, retornando o contrato estruturado; entrypoint `python -m chat_ram.conhecimento [--transporte stdio|streamable-http|sse]`.
- **Agente** (`conversa.py`): o adapter do modelo passou a acumular `tool_calls` no stream (`modelo.stream_eventos`); o agente executa a ferramenta, faz **map-reduce** (resume bloco a bloco e consolida) quando `cobertura_parcial`, e então responde. Ligado à API em `main.py` (`create_app(modelo, settings, agente)`), sem regredir o streaming da issue 01.
- **Tool calling validado** no proxy free (`nvidia/nemotron-3-super-120b-a12b:free`): devolve `tool_calls` com `consultar_ticket` e argumentos corretos.
- **Testes**: 56 no total — núcleo com fakes, integração com o PostgreSQL 18 (ticket real e inexistente), servidor MCP (`list_tools`/`call_tool`, inclusive falha técnica) e agente (executa ferramenta, não encontrado não inventa, resumo por blocos). `ruff` e `mypy --strict` verdes.
- **Evidência real** (mock + OpenRouter free): pedir `2026011600004` → o agente chamou a ferramenta e resumiu problema/investigação/solução com as fontes; pedir um número inexistente → respondeu que não há no histórico.
- Pendente para aceite humano: validar na **base real** e via **Open WebUI**; e migrar o loop do agente para LangGraph quando a persistência entrar (issue 04). Por isso `ready-for-human`.
