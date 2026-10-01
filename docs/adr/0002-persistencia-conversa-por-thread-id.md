# Persistência da conversa por thread_id

Status: accepted

O estado de cada conversa é persistido pelo checkpointer do LangGraph, chaveado por `thread_id`, no PostgreSQL 18 em schema próprio — separado dos dados OTRS, que permanecem somente-leitura. Uma tabela `chat` no mesmo schema guarda o vínculo entre o id do chat na interface, o `thread_id` e metadados (usuário, título, datas), permitindo retomar a conversa depois de fechar a interface. O estado conserva fila selecionada, ticket em foco e esclarecimentos pendentes.

## Consequences
- Conversas diferentes não compartilham contexto.
- É preciso definir e validar como a interface fornece um identificador estável de conversa ao backend.
