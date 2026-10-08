# Persistência da conversa em tabelas próprias

Status: accepted

O estado da conversa é persistido em **tabelas próprias** no PostgreSQL 18, em schema `conversa` (configurável por `CONVERSA_SCHEMA`), separado dos dados OTRS (somente-leitura): `chat` (vínculo `chat_id` da interface ↔ `thread_id`, com metadados), `mensagem` (histórico por `thread_id`, com idempotência por requisição) e `estado` (fila selecionada, ticket em foco, esclarecimentos). A escolha difere do ADR-0002, que previa o checkpointer do LangGraph: o agente desta versão é um loop próprio (`conversa.py`), sem `StateGraph`, então o checkpointer não teria estado de grafo a persistir. O `thread_id` continua sendo a chave estável, como no ADR-0002.

## Decisões

- **Identificador estável**: a interface envia o id da conversa em `X-Conversation-Id` (e a requisição em `X-Request-Id`); sem eles, a API gera um id. O `thread_id` é criado no primeiro contato e reusado depois.
- **Histórico autoritativo**: o backend usa o histórico persistido por `thread_id` mais a última mensagem do usuário, ignorando o histórico reenviado pela interface — evita duplicação quando a UI reenvia o contexto.
- **Idempotência**: `mensagem` tem `UNIQUE (thread_id, request_id, papel)`; retentativa da mesma requisição não duplica mensagens.
- **Isolamento**: tudo é chaveado por `thread_id`; conversas diferentes não compartilham contexto.

## Considered Options

- **Checkpointer do LangGraph** (ADR-0002): mantido como opção futura, se o agente migrar para um `StateGraph`; aí o estado do grafo passa a ser persistido pelo checkpointer e as tabelas `mensagem`/`estado` podem ser revistas.

## Consequences

- Trocar de banco/schema exige recriar as tabelas; `garantir_estrutura` é idempotente.
- A migração para LangGraph, se ocorrer, precisa reconciliar o vínculo `chat`↔`thread_id` e a idempotência por requisição.
