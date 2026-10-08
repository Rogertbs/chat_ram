# AGENTS.md

Instruções para agentes de código neste repositório.

## Projeto

`chat_ram` — assistente de chat que ajuda o analista de helpdesk a consultar o histórico do OTRS (buscar casos semelhantes e entender tickets), com evidências conferíveis. Escopo da primeira entrega em `docs/mvp-0.1.md`; arquitetura em `docs/arquitetura-0.1.md`.

## Dados de desenvolvimento

Para desenvolver sem os dados reais do OTRS, use o banco mock (`mock/`, ver `docs/mock.md`): gere com `python mock/gerar_banco.py --recriar` e aponte `POSTGRES18_DB=otrs_mock` no `.env`. Nenhum ticket real sai da máquina.

## Agent skills

### Issue tracker

Issues de desenvolvimento vivem localmente em `docs/tickets/<feature>/` (um arquivo por issue). See `docs/agents/issue-tracker.md`.

### Triage labels

Cinco labels canônicos: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` e `docs/adr/` na raiz. See `docs/agents/domain.md`.
