# PostgreSQL 18 para a aplicação RAG

O banco de dados da aplicação é um contêiner PostgreSQL **18.6** com **pgvector 0.8.6** e **pg_textsearch 1.4.0** (BM25). O Compose fica em `postgres18/docker-compose.yml`; a imagem é construída por `postgres18/Dockerfile`. `pg_textsearch` é a extensão BM25 escolhida para este projeto.

O PostgreSQL 15 migrado continua separado na porta local `5433` e contém o banco OTRS. O PostgreSQL 18 atende na porta local `5435` e tem um volume próprio. **Os dados OTRS ainda não foram copiados para o PostgreSQL 18**; apenas o servidor e as extensões foram instalados e testados.

## Subir e conferir

Execute a partir da raiz do projeto:

```bash
docker compose --env-file .env -f postgres18/docker-compose.yml up -d --build --wait
docker compose --env-file .env -f postgres18/docker-compose.yml exec postgres18 \
  psql -U otrs -d otrs -c "SELECT extname, extversion FROM pg_extension WHERE extname IN ('vector', 'pg_textsearch');"
```

A senha do novo banco está em `POSTGRES18_PASSWORD` no `.env` local (permissão `0600`). Para uma aplicação no host, use `127.0.0.1:5435`, banco `otrs` e usuário `otrs`. Para outra aplicação Docker, conecte-a à rede `chat_ram_rag_data` e use `postgres18:5432`.

O volume do PostgreSQL 18 é montado em `/var/lib/postgresql`, conforme o layout novo da imagem oficial. O script `postgres18/init/001-extensions.sql` cria as extensões somente quando o volume é inicializado pela primeira vez. O servidor inicia com `shared_preload_libraries=pg_textsearch`, exigido pela extensão BM25.

## Como as buscas se complementam

`pgvector` faz busca por proximidade entre embeddings; ela encontra trechos semanticamente parecidos mesmo quando usam palavras diferentes. `pg_textsearch` faz busca lexical com ranking BM25; ela ajuda quando a pergunta contém número de chamado, nome exato, código ou termo específico. A tool de RAG pode consultar os dois índices de uma tabela de trechos e combinar os resultados antes de entregar contexto ao modelo.

Depois que a aplicação criar e preencher uma tabela de trechos com `content text` e `embedding vector(N)` (onde `N` depende do modelo de embeddings), os índices podem ser criados assim:

```sql
CREATE INDEX rag_chunks_bm25 ON rag_chunks USING bm25(content)
  WITH (text_config='portuguese');

CREATE INDEX rag_chunks_vector ON rag_chunks USING hnsw (embedding vector_cosine_ops);
```

O BM25 consulta `content <@> 'termos da busca'` e ordena pelos menores escores; a busca vetorial pode ordenar por `embedding <=> :embedding_da_pergunta`. O teste de instalação criou um índice BM25 em português, retornou o documento esperado e confirmou distância vetorial zero para vetores idênticos. Tudo ocorreu em uma transação revertida, sem deixar tabela de teste.

Para copiar o banco OTRS do PostgreSQL 15 para o 18 em outra etapa, use dump/restore lógico e compare contagens, índices e os sete valores de texto originais guardados nas tabelas auxiliares. A cópia dos dados não faz parte da instalação das extensões.

Fontes: [PostgreSQL 18.6](https://www.postgresql.org/docs/release/18.6/), [pgvector](https://github.com/pgvector/pgvector), [pg_textsearch](https://github.com/timescale/pg_textsearch), [layout do volume PostgreSQL 18](https://github.com/docker-library/docs/blob/master/postgres/README.md).
