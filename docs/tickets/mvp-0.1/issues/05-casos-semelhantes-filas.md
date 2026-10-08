# 05: Casos semelhantes e resolução de filas

**What to build:** A ferramenta `buscar_casos(pergunta, filas?)` com busca híbrida (BM25 + vetor) fundida por RRF (`k=60`), desempate por similaridade de cosseno e threshold de cosseno configurável (provisório 0,5), retornando os melhores trechos com suas fontes. Mais a ferramenta `resolver_filas(texto)`, que devolve candidatos e pede esclarecimento quando o nome é ambíguo. O filtro de fila é aplicado às duas buscas.

**Blocked by:** 02 — Preparação do histórico; 03 — Servidor MCP e consulta por ticket

**Status:** ready-for-human

- [x] Descrever um problema retorna casos semelhantes com fontes rastreáveis
- [x] "Buscar só na fila X" restringe a busca; nome ambíguo faz o agente pedir esclarecimento
- [x] Sem resultados suficientes, o sistema declara o alcance da busca em vez de preencher com matches fracos
- [x] Casos com soluções diferentes aparecem com seus respectivos contextos e referências

## Comments

- Núcleo em `conhecimento/busca.py`: `buscar_casos` embeda a pergunta (mesmo modelo dos trechos), traz 50 candidatos de cada índice, funde por **RRF** (`sum(1/(60+posição))`), calcula a **similaridade de cosseno** de cada candidato, aplica o **threshold 0,5** e ordena por RRF, cosseno e chave determinística, devolvendo os **8 melhores** com fonte (`tn`, `article_id`, `posicao`, `fila`, `data`, visibilidade). Sem nada acima do threshold, `alcance_suficiente=false` com mensagem — não preenche com matches fracos. `resolver_filas` casa o texto com as filas (exato → único; parcial com mais de um → `ambiguo`).
- Repositório: `PostgresTrechos.similaridades` (uma query para os candidatos fundidos) e `PostgresTickets.listar_filas`.
- Ferramentas do agente (`conversa.py`): `buscar_casos` e `resolver_filas`, com um **contexto** mutável por conversa que carrega a `fila_selecionada` e o `ticket_em_foco`. O filtro de fila é aplicado às duas buscas; restringir a uma fila a persiste, e o nome ambíguo deixa o modelo pedir esclarecimento. O `Agente.stream` passou a receber esse contexto (substitui o callback `ao_ferramenta`).
- Servidor MCP (`conhecimento/mcp.py`) expõe `consultar_ticket`, `buscar_casos` e `resolver_filas`.
- **Testes** (80 no total): RRF/desempate/threshold/filtro, resolução de filas (exato, ambíguo, vazio), ferramentas do agente (busca com fontes, fila no contexto), MCP (ferramentas listadas, `resolver_filas`) e integração (`similaridades`, `listar_filas`). `ruff` e `mypy --strict` verdes.
- **Evidência real** (mock + OpenRouter free): descrever "tronco SIP sem áudio em uma direção" retornou o caso `2026011600004` com fonte (ticket, article_id, data); restringir à fila `Nivel 2` manteve o caso e o filtro.
- Pendente para aceite humano: validar sobre a base real (a preparação ainda não rodou nela) e com a Open WebUI. Por isso `ready-for-human`.
