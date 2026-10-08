# 06: Ticket em foco, evidências e sugestão do modelo

**What to build:** O ticket consultado vira foco para as perguntas seguintes, mantendo o contexto. Toda conclusão sobre o histórico traz referência conferível (número e título do ticket, data, trecho do artigo). Quando não houver solução documentada, o sistema declara a ausência e apresenta uma alternativa sob o rótulo "Sugestão do modelo — não validada no histórico". Consultar pelo número um ticket fora do filtro de fila informa a fila do ticket e preserva o filtro para as buscas seguintes.

**Blocked by:** 03 — Servidor MCP e consulta por ticket; 04 — Conversa persistente; 05 — Casos semelhantes e resolução de filas

**Status:** ready-for-human

- [x] Perguntas seguintes usam o contexto daquele ticket
- [x] Referências apontam para fontes efetivamente retornadas — sem número ou data inventados
- [x] Ausência de solução documentada é declarada e a sugestão do modelo vem em seção separada
- [x] Ticket fora do filtro informa sua fila e preserva o filtro

## Comments

- Prompt de sistema (`conversa.py`, `SISTEMA`) com as regras do domínio: citar fonte conferível (número e título, data, article_id); nunca inventar número/data/trecho; informar a fila ao consultar por número, sem alterar o filtro; declarar ausência de solução documentada e apresentar a alternativa sob o rótulo exato **"Sugestão do modelo — não validada no histórico"**; não atribuir sugestões aos tickets.
- **Ticket em foco**: quando há `ticket_em_foco` no estado e a nova mensagem não traz um número, `Conversa` injeta o conteúdo do ticket (artigos com `article_id`/data/visibilidade, com corte e aviso de cobertura parcial) como contexto, para as perguntas seguintes. Consultar um novo número não injeta o foco antigo.
- **Filtro preservado**: `consultar_ticket` não toca em `fila_selecionada`; o resultado traz a fila do ticket, então a consulta explícita informa a fila e mantém o filtro das buscas seguintes.
- **Testes** (84 no total): prompt de sistema com o rótulo; follow-up usando o conteúdo do ticket em foco; número na mensagem não injeta o foco; consulta por número preserva o filtro e traz a fila. `ruff` e `mypy --strict` verdes.
- **Evidência real** (mock + OpenRouter free): após consultar `2026011600004`, "E qual foi a solução aplicada?" respondeu com a solução citando o `article_id` e o TN; uma pergunta sem caso documentado declarou a ausência e apresentou a alternativa sob o rótulo exato.
- Pendente para aceite humano: validar com a Open WebUI e na base real. Por isso `ready-for-human`.
