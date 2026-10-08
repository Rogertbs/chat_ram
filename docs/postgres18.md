# PostgreSQL 18 para a aplicação RAG

O banco de dados da aplicação é um contêiner PostgreSQL **18.6** com **pgvector 0.8.6** e **pg_textsearch 1.4.0** (BM25). O Compose fica em `postgres18/docker-compose.yml`; a imagem é construída por `postgres18/Dockerfile`. `pg_textsearch` é a extensão BM25 escolhida para este projeto.

O PostgreSQL 15 migrado continua separado na porta local `5433` e contém o banco OTRS. O PostgreSQL 18 atende na porta local `5435`, tem um volume próprio e **já recebeu uma cópia validada de todos os dados OTRS**. Os índices BM25 e vetoriais para os trechos de RAG ainda dependem da criação e do preenchimento dessas tabelas pela aplicação.

## Subir e conferir

Execute a partir da raiz do projeto:

```bash
docker compose --env-file .env -f postgres18/docker-compose.yml up -d --build --wait
docker compose --env-file .env -f postgres18/docker-compose.yml exec postgres18 \
  psql -U otrs -d otrs -c "SELECT extname, extversion FROM pg_extension WHERE extname IN ('vector', 'pg_textsearch');"
```

A senha do novo banco está em `POSTGRES18_PASSWORD` no `.env` local (permissão `0600`). Para uma aplicação no host, use `127.0.0.1:5435`, banco `otrs` e usuário `otrs`. Para outra aplicação Docker, conecte-a à rede `chat_ram_rag_data` e use `postgres18:5432`.

O volume do PostgreSQL 18 é montado em `/var/lib/postgresql`, conforme o layout novo da imagem oficial. O script `postgres18/init/001-extensions.sql` cria as extensões somente quando o volume é inicializado pela primeira vez. O servidor inicia com `shared_preload_libraries=pg_textsearch`, exigido pela extensão BM25.

## Acesso externo (DBeaver)

Por padrão o PostgreSQL 18 publica a porta apenas em localhost (`127.0.0.1:5435`). Para conectar de outra máquina, o `postgres18/docker-compose.yml` publica `5435:5432` (todas as interfaces) e o `pg_hba.conf` aceita **somente o usuário `otrs`, com senha**; qualquer outro usuário ou origem é recusado. Aplique ou reaplique a restrição no container em execução:

```bash
postgres18/restrict-hba.sh
```

Conexões:
- Banco real (cópia OTRS): host `<IP-do-servidor>`, porta `5435`, banco `otrs`
- Banco mock: mesma porta, banco `otrs_mock`
- Usuário `otrs`; senha em `POSTGRES18_PASSWORD` no `.env`.

Recomenda-se **túnel SSH** em vez de expor a porta publicamente. Se expuser:
- Libere a porta 5435 apenas no firewall/security group necessário.
- O `otrs` é superusuário e a senha é a única barreira; rotacione-a se vazar.
- O Docker pode ignorar o `ufw` do host (regras na cadeia DOCKER); restrinja no security group do provedor.

Para voltar a só localhost, troque `ports` para `"127.0.0.1:5435:5432"` no compose e rode `docker compose --env-file .env -f postgres18/docker-compose.yml up -d`.

## Como as buscas se complementam

`pgvector` faz busca por proximidade entre embeddings; ela encontra trechos semanticamente parecidos mesmo quando usam palavras diferentes. `pg_textsearch` faz busca lexical com ranking BM25; ela ajuda quando a pergunta contém número de chamado, nome exato, código ou termo específico. A tool de RAG pode consultar os dois índices de uma tabela de trechos e combinar os resultados antes de entregar contexto ao modelo.

Depois que a aplicação criar e preencher uma tabela de trechos com `content text` e `embedding vector(N)` (onde `N` depende do modelo de embeddings), os índices podem ser criados assim:

```sql
CREATE INDEX rag_chunks_bm25 ON rag_chunks USING bm25(content)
  WITH (text_config='portuguese');

CREATE INDEX rag_chunks_vector ON rag_chunks USING hnsw (embedding vector_cosine_ops);
```

O BM25 consulta `content <@> 'termos da busca'` e ordena pelos menores escores; a busca vetorial pode ordenar por `embedding <=> :embedding_da_pergunta`. O teste de instalação criou um índice BM25 em português, retornou o documento esperado e confirmou distância vetorial zero para vetores idênticos. Tudo ocorreu em uma transação revertida, sem deixar tabela de teste.

## Migração dos dados OTRS

Em 15/09/2026, o banco PostgreSQL 15 foi exportado com `pg_dump --format=custom --no-owner --no-privileges` e restaurado no PostgreSQL 18 vazio com `pg_restore --jobs=4 --exit-on-error`. O dump incluiu as 195 tabelas OTRS e as duas tabelas auxiliares `otrs_migration_raw_article_body` e `otrs_migration_raw_text`, que guardam os bytes originais de sete textos alterados na conversão inicial do MariaDB.

Execute `python3 verify_pg18.py` na raiz do projeto para comparar a origem e o destino. A validação já passou para 197 tabelas, 14.228.591 registros (14.228.584 OTRS + 7 auxiliares), 47 colunas `bytea` com 238.612.129 bytes, 1.499 colunas e tipos, 231 restrições, 721 índices, 153 sequências e seus estados, além dos textos originais preservados. As extensões `vector 0.8.6` e `pg_textsearch 1.4.0` permaneceram habilitadas no PostgreSQL 18. A origem PostgreSQL 15 continua disponível para comparação.

## Backup de segurança do PostgreSQL 18

O backup lógico completo do banco `otrs` foi criado com `pg_dump --format=custom` em 15/09/2026: `backups/otrs-postgres18-20260915T205353Z.dump` (471 MiB, permissão `0600`). O arquivo é ignorado pelo Git; copie-o junto com `backups/otrs-postgres18-20260915T205353Z.dump.sha256` para o local em que você guarda backups. Para conferir a cópia, execute a partir da raiz do projeto:

```bash
(cd backups && sha256sum --check otrs-postgres18-20260915T205353Z.dump.sha256)
```

O arquivo foi restaurado integralmente em um banco temporário separado, `otrs_backup_check`. O verificador `python3 verify_pg18.py --target-db otrs_backup_check` conferiu as mesmas 197 tabelas, contagens, dados binários, colunas, chaves, índices, sequências e sete textos originais. A restauração também recriou `vector 0.8.6` e `pg_textsearch 1.4.0`. O banco temporário foi removido após o teste; o banco de desenvolvimento `otrs` permaneceu intacto.

Para restaurar futuramente, use um servidor PostgreSQL 18 vazio com a imagem deste Compose, que já contém os binários das duas extensões. O dump guarda os objetos e dados do banco, mas não as senhas nem as configurações globais do servidor. Restaure em um banco novo para preservar o `otrs` atual:

```bash
docker compose --env-file .env -f postgres18/docker-compose.yml exec -T postgres18 \
  createdb -U otrs otrs_restaurado
docker compose --env-file .env -f postgres18/docker-compose.yml exec -T postgres18 \
  pg_restore --exit-on-error -U otrs -d otrs_restaurado \
  < backups/otrs-postgres18-20260915T205353Z.dump
```

Fontes: [PostgreSQL 18.6](https://www.postgresql.org/docs/release/18.6/), [pgvector](https://github.com/pgvector/pgvector), [pg_textsearch](https://github.com/timescale/pg_textsearch), [layout do volume PostgreSQL 18](https://github.com/docker-library/docs/blob/master/postgres/README.md).
