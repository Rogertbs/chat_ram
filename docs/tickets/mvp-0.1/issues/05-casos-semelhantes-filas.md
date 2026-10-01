# 05: Casos semelhantes e resolução de filas

**What to build:** A ferramenta `buscar_casos(pergunta, filas?)` com busca híbrida (BM25 + vetor) fundida por RRF (`k=60`), desempate por similaridade de cosseno e threshold de cosseno configurável (provisório 0,5), retornando os melhores trechos com suas fontes. Mais a ferramenta `resolver_filas(texto)`, que devolve candidatos e pede esclarecimento quando o nome é ambíguo. O filtro de fila é aplicado às duas buscas.

**Blocked by:** 02 — Preparação do histórico; 03 — Servidor MCP e consulta por ticket

**Status:** ready-for-agent

- [ ] Descrever um problema retorna casos semelhantes com fontes rastreáveis
- [ ] "Buscar só na fila X" restringe a busca; nome ambíguo faz o agente pedir esclarecimento
- [ ] Sem resultados suficientes, o sistema declara o alcance da busca em vez de preencher com matches fracos
- [ ] Casos com soluções diferentes aparecem com seus respectivos contextos e referências
