# 02: Preparação do histórico

**What to build:** O módulo de Preparação — um pipeline em lote que lê a cópia fixa do OTRS no PostgreSQL 18, normaliza HTML, segmenta em trechos (um por artigo; divide acima de ~2.000 caracteres com ~200 de sobreposição), gera embeddings com o Qwen3-Embedding-0.6B (1024 dimensões) pelo proxy LiteLLM e grava a tabela de trechos com os índices BM25 (português) e HNSW. Emite um relatório de textos vazios, falhas de conversão, quantidades e cobertura por fila.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Tabela de trechos criada com metadados: `tn`, `article_id`, fila, data, visibilidade, posição, versão de processamento e modelo de embeddings
- [ ] Índices BM25 e HNSW criados; a busca lexical e a vetorial retornam os trechos esperados com suas fontes
- [ ] Retomada sem duplicações; vetores de modelos/dimensões diferentes não se misturam
- [ ] Relatório de preparação emitido (vazios, falhas, contagens, cobertura)
