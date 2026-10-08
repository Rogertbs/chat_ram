# Banco mock para desenvolvimento

Para desenvolver e validar o sistema **sem expor os dados reais do OTRS** (por exemplo, ao apontar a Preparação para um proxy externo como o OpenRouter), use o banco mock: um PostgreSQL separado, com poucos chamados **fictícios** de Asterisk/telecom. Nada do banco `otrs` real é tocado.

O diretório `mock/` tem:

- `mock/dados.json` — 10 chamados fictícios em 3 filas (`Nivel 1`, `Nivel 2`, `Nivel 3`), com casos de borda de propósito: artigo longo (> 2.000 caracteres, testa a divisão), artigo de corpo vazio (testa `textos_vazios`), artigo com HTML, nota interna (`is_visible_for_customer = 0`) e tickets com vários artigos.
- `mock/gerar_banco.py` — cria o banco, o subconjunto de tabelas OTRS que a Preparação lê e insere os chamados do JSON.

## Gerar o banco

Com o PostgreSQL 18 no ar (ver [postgres18.md](postgres18.md)) e o `.env` com `POSTGRES18_PASSWORD`:

```bash
python mock/gerar_banco.py --recriar
```

O script é idempotente: recria as tabelas e reinsere os dados a cada execução. `--recriar` também apaga e recria o banco inteiro. Opções: `--banco`, `--dados`, `--manutencao`.

As extensões `vector` e `pg_textsearch` são criadas no banco mock. O script usa o banco `postgres` só para criar o banco mock.

## Usar em desenvolvimento

Aponte o `.env` para o mock e para o proxy de desenvolvimento:

```env
POSTGRES18_DB=otrs_mock
LITELLM_BASE_URL=https://openrouter.ai/api
LITELLM_API_KEY=sk-or-v1-...
MODEL_ALIAS=nvidia/nemotron-3-super-120b-a12b:free
EMBEDDING_MODEL=nvidia/nemotron-3-embed-1b:free
EMBEDDING_DIMENSION=1024
EMBEDDING_TRUNCATE_TO=1024
EMBEDDING_BATCH=16
```

O Nemotron free é nativo em 2048; `EMBEDDING_TRUNCATE_TO=1024` corta localmente para as primeiras 1024 dimensões e renormaliza em L2 (MRL), mantendo o schema `vector(1024)` do ADR-0001. O HNSW do pgvector não indexa acima de 2000 dimensões, então 1024 é o alvo seguro.

Rode a Preparação:

```bash
python -m chat_ram.preparacao
```

Como são só 10 chamados, não é preciso `--limite`. O relatório sai em JSON com vazios, falhas, contagens e cobertura por fila. A tabela `rag.trechos` e os índices BM25/HNSW são criados dentro do próprio banco mock.

> **Privacidade:** com o mock, nenhum ticket real é enviado a terceiros. Ao voltar para a base real, use apenas o proxy fornecido ao projeto (ver [postgres18.md](postgres18.md) e [arquitetura-0.1.md](arquitetura-0.1.md)); não aponte dados reais para provedores externos.

## Subir o serviço com Docker

Há um `Dockerfile` e um `docker-compose.yml` na raiz, mais um `Makefile`. A imagem instala as dependências sozinha (não é preciso instalar nada no host).

```bash
make prod   # sobe o PostgreSQL 18 + o serviço (build + up)
make dev    # prod + banco mock + preparação, e recria o serviço
```

- `make prod` — sobe o PG18 e o serviço `chat_ram` (API na porta `8000`), conectado à rede `chat_ram_rag_data`.
- `make dev` — ambiente de teste pronto: (re)gera o banco mock, roda a preparação e recria o serviço.
- `make ui` — sobe a **Open WebUI** em `http://localhost:3000`, já apontada para a API (`OPENAI_API_BASE_URL=http://app:8000/v1`, `WEBUI_AUTH=false`). A primeira subida demora alguns minutos (baixa o modelo de embedding padrão); depois fica em cache.
- `make db` / `make build` / `make up` / `make mock` / `make prep` / `make down` / `make logs` / `make test` — alvos individuais (`make help` lista tudo).

A API fica em `http://127.0.0.1:8000` (`/v1/models`, `/v1/chat/completions`; Swagger em `/docs`) e a interface em `http://localhost:3000`. O container usa `POSTGRES18_HOST=postgres18`/`PORT=5432` (rede Docker) por cima do `.env`, e o banco continua sendo o `otrs_mock`.

> A Open WebUI reenvia o histórico da conversa a cada mensagem. Como ela não envia um id de conversa, o backend usa esse histórico reenviado (a retomada por `thread_id` da issue 04 só vale quando há um id de conversa, o que exige uma extensão da UI).

> Os modelos `:free` do OpenRouter são **intermitentes** no tool calling: às vezes devolvem a chamada como texto. Repetir a requisição costuma resolver; com o proxy definitivo isso não deve ocorrer.

## Voltar para a base real

Troque no `.env`:

```env
POSTGRES18_DB=otrs
```

e restaure a configuração de embeddings do projeto (`EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B`, `EMBEDDING_DIMENSION=1024`). A guarda de modelo/dimensão em `rag.config` recusa misturar vetores de modelos diferentes — se já houver trechos do mock, gere-os em um banco ou schema diferente, ou reprocesse do zero.

## Gerar em outra máquina

Copie o diretório `mock/` e rode `python mock/gerar_banco.py --recriar` com o `.env` daquele ambiente. Só é necessário o PostgreSQL 18 com `pgvector` e `pg_textsearch`.

## Editar os chamados

Altere `mock/dados.json` (filas e chamados) e rode `python mock/gerar_banco.py` de novo. Mantenha os casos de borda para continuar exercitando a divisão de artigos longos, a normalização de HTML, os textos vazios e as notas internas.
