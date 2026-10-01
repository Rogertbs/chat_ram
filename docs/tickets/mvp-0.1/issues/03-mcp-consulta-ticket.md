# 03: Servidor MCP e consulta por ticket

**What to build:** O servidor FastMCP com a ferramenta `consultar_ticket(numero, pergunta?)`, conectado ao backend LangGraph como cliente. O agente chama a ferramenta quando o usuário informa um número de ticket e entrega um resumo cronológico (problema, tentativas, solução documentada, situação) com fontes conferíveis, distinguindo ticket não encontrado, fila ambígua e falha técnica.

**Blocked by:** 01 — Chat streaming de ponta a ponta

**Status:** ready-for-agent

- [ ] Pedir um número de ticket na conversa retorna o resumo cronológico com referências conferíveis
- [ ] Número inexistente é reportado como não encontrado — o ticket nunca é inventado
- [ ] Ticket extenso é resumido em blocos cronológicos, sinalizando cobertura parcial
- [ ] O contrato do proxy (tool calling) foi validado antes de depender dele
