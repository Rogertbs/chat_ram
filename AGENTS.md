# AGENTS.md

Instruções para agentes de código neste repositório.

## Projeto

`chat_ram` — assistente de chat que ajuda o analista de helpdesk a consultar o histórico do OTRS (buscar casos semelhantes e entender tickets), com evidências conferíveis. Escopo da primeira entrega em `docs/mvp-0.1.md`; arquitetura em `docs/arquitetura-0.1.md`.

## Agent skills

### Issue tracker

Issues de desenvolvimento vivem localmente em `docs/tickets/<feature>/` (um arquivo por issue). See `docs/agents/issue-tracker.md`.

### Triage labels

Cinco labels canônicos: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` e `docs/adr/` na raiz. See `docs/agents/domain.md`.
