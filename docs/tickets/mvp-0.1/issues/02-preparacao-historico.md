# 02: Preparação do histórico

**What to build:** O módulo de Preparação — um pipeline em lote que lê a cópia fixa do OTRS no PostgreSQL 18, normaliza HTML, segmenta em trechos (um por artigo; divide acima de ~2.000 caracteres com ~200 de sobreposição), gera embeddings com o Qwen3-Embedding-0.6B (1024 dimensões) pelo proxy LiteLLM e grava a tabela de trechos com os índices BM25 (português) e HNSW. Emite um relatório de textos vazios, falhas de conversão, quantidades e cobertura por fila.

**Blocked by:** None (can start immediately)

**Status:** needs-info

- [x] Tabela de trechos criada com metadados: `tn`, `article_id`, fila, data, visibilidade, posição, versão de processamento e modelo de embeddings
- [x] Índices BM25 e HNSW criados; a busca lexical e a vetorial retornam os trechos esperados com suas fontes
- [x] Retomada sem duplicações; vetores de modelos/dimensões diferentes não se misturam
- [x] Relatório de preparação emitido (vazios, falhas, contagens, cobertura)

## Comments

- Implementado o módulo `preparacao` (`src/chat_ram/preparacao/`): leitura da cópia fixa (`PostgresHistorico`), normalização de HTML e segmentação por artigo (2.000/200), embeddings pelo contrato OpenAI `/v1/embeddings` (`LiteLLMEmbeddings`), tabela `rag.trechos` com índices BM25 (português) e HNSW (cosseno), retomada idempotente por `(article_id, posicao, versao)` e guarda de modelo/dimensão na tabela `rag.config`, além de relatório com vazios, falhas de conversão, contagens e cobertura por fila. Entrypoint: `python -m chat_ram.preparacao`.
- Testes: unitários de texto/segmentação, embeddings (respx) e orquestração com fakes; integração real com o PostgreSQL 18 cobrindo criação de índices, busca lexical/vetorial com fonte, filtro de fila, idempotência e recusa de modelo/dimensão incompatível. `pytest` (37), `ruff` e `mypy --strict` verdes.
- Pendente: execução real sobre toda a base com o proxy de embeddings, que depende do alias/base/chave do proxy no `.env` (mesmo bloqueio da issue 01). Por isso `needs-info`.

