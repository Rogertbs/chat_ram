# Embeddings: Qwen3-Embedding-0.6B com 1024 dimensões

Status: accepted

Decidimos gerar os embeddings dos trechos e das perguntas com o `Qwen/Qwen3-Embedding-0.6B` servido pelo proxy **LiteLLM** pelo contrato padrão `/v1/embeddings` (OpenAI-compatible), produzindo vetores de **1024 dimensões**, normalizados e comparados por distância de cosseno no `pgvector`. A aplicação apenas aponta o IP/base e o nome do modelo no `.env`; não há serviço de embeddings próprio. O mesmo modelo e a mesma configuração valem para documentos e perguntas. O modelo foi escolhido por ser pequeno e multilíngue (cobre o português e as filas em inglês/espanhol); a dimensão fica fixa na coluna vetorial.

## Considered Options
- Modelos maiores (`Qwen3-Embedding-4B`/`8B`, `BGE-M3`): melhor recall, mais custo e VRAM.
- `gte-Qwen2-1.5B-instruct`: geração anterior da família.

## Consequences
- A tabela de trechos usa `embedding vector(1024)` com índice HNSW (cosseno).
- Trocar de modelo ou de dimensão exige reprocessar todos os trechos; não misturar vetores de modelos/dimensões diferentes.
