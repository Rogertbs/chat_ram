# Migração do backup OTRS para PostgreSQL

Este diretório contém dois projetos Compose separados: `mariadb/docker-compose.yml` e `postgres/docker-compose.yml`. Eles compartilham uma rede Docker chamada `otrs_migration` e guardam os dados em volumes persistentes. As portas ficam disponíveis somente em `127.0.0.1` (MariaDB `3307`, PostgreSQL `5433`).

O MariaDB 10.11 é usado como etapa de restauração do dump produzido no MariaDB 10.2. O PostgreSQL 15 é o destino. `pgloader` lê o banco MariaDB em execução, converte tipos (inclusive BLOB para `bytea`), cria tabelas, copia dados e ajusta sequências. A transferência coloca as tabelas no esquema `public`. Neste backup, o `pgloader` não criou os índices; `repair_schema.py` os reconstrói a partir do catálogo do MariaDB junto com as chaves primárias e estrangeiras.

Execute a partir deste diretório:

```bash
./restore.sh
./migrate.sh
```

`restore.sh` importa `BackpOtrs.sql` via stdin e só aceita o MariaDB vazio. `migrate.sh` exige as 195 tabelas restauradas e o esquema `public` vazio no PostgreSQL. Se uma etapa falhar, examine o erro antes de repetir: os scripts não apagam volumes ou dados existentes.

`migrate.sh` chama `repair_schema.py`, `preserve_text.py`, `preserve_more_text.py` e `verify.py` ao final. A verificação calcula contagens exatas para todas as 195 tabelas, compara os bytes das 45 colunas binárias e confere chaves, índices e os valores de texto preservados.

## Resultado desta execução

O backup foi restaurado e migrado nesta máquina. A conferência encontrou 14.228.584 registros em cada banco, 156 chaves primárias, 72 chaves estrangeiras e 719 índices nas tabelas originais de ambos. As 45 colunas binárias somam 238.601.561 bytes em cada banco.

A auditoria de 477 colunas de texto encontrou alterações em três colunas. Comparações por hash localizaram cinco valores de `article_data_mime.a_body`, um de `article_data_mime.a_subject` e um de `article_search_index.article_value` alterados pelo `pgloader`. Os bytes exatos da origem foram copiados para `public.otrs_migration_raw_article_body` e `public.otrs_migration_raw_text` no PostgreSQL, com hash e tamanho conferidos. Os valores principais dessas sete linhas continuam na forma UTF-8 aceita pelo PostgreSQL; as tabelas auxiliares guardam a versão original, inclusive bytes inválidos ou nulos que o tipo `text` não pode armazenar.

Uma validação funcional no OTRS ainda é necessária antes de apontar a aplicação para o novo banco.

O arquivo `.env` guarda senhas geradas localmente e deve permanecer privado. O dump SQL sozinho pode não conter arquivos da aplicação, configuração e artigos/anexos guardados no filesystem. Para operar o OTRS sobre PostgreSQL, use a mesma versão do sistema e os mesmos módulos do banco original, configure o driver PostgreSQL no `Kernel/Config.pm` e valide o esquema contra os scripts PostgreSQL distribuídos com aquela versão. Uma cópia feita pelo `pgloader` não substitui essa validação funcional.
