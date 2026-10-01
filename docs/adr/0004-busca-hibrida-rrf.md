# Busca híbrida: BM25 + vetor fundidos por RRF

Status: accepted

A busca de casos semelhantes usa dois índices sobre a tabela de trechos: **BM25** (`pg_textsearch`, `text_config='portuguese'`) sobre o texto e **HNSW** (`pgvector`, `vector_cosine_ops`) sobre o embedding `vector(1024)`. O filtro de fila é aplicado **antes** da fusão, nas duas buscas. Cada busca traz **50 candidatos**, fundidos por **RRF** (`sum(1/(60 + posição))`, `k=60`), **sem reranker**. O desempate é por **similaridade de cosseno** (maior melhor) e depois por id determinístico (`tn`, `article_id`). Aplica-se um **threshold de cosseno mínimo de 0,5** (configurável no `.env`); abaixo dele, não se preenche com matches fracos − declara-se alcance insuficiente. Os **8 melhores trechos** após o threshold vão ao LLM.

## Considered Options
- **Reranker cross-encoder** (`Qwen3-Reranker-0.6B`): melhor precisão no topo, mas é uma etapa e um modelo a mais. Rejeitado para o MVP; reconsiderar se a avaliação das 20 perguntas mostrar erro no top-8.
- **Score fusion** (somar BM25 e cosseno direto): rejeitado, mistura escalas diferentes.

## Consequences
- O threshold e as quantidades (50/8) são parâmetros calibrados na avaliação de aceite.
- Sem reranker, a qualidade do topo depende da fusão por posição do RRF.
