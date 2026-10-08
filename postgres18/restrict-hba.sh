#!/usr/bin/env bash
# Restringe o pg_hba.conf do PostgreSQL 18: acesso externo somente ao usuário otrs.
# Idempotente. Uso: postgres18/restrict-hba.sh [nome-do-container]
set -euo pipefail

container="${1:-chat-ram-postgres18-postgres18-1}"

docker exec -i "$container" sh -c 'cp "$PGDATA/pg_hba.conf" "$PGDATA/pg_hba.conf.bak.$(date +%s)"; cat > "$PGDATA/pg_hba.conf"' <<'HBA'
# TYPE  DATABASE        USER            ADDRESS                 METHOD

# Acesso local (socket, dentro do contêiner)
local   all             all                                     trust

# Acesso local pelo host
host    all             all             127.0.0.1/32            trust
host    all             all             ::1/128                 trust

# Replicação local
local   replication     all                                     trust
host    replication     all             127.0.0.1/32            trust
host    replication     all             ::1/128                 trust

# Acesso externo: somente o usuário otrs, com senha
host    all             otrs            all                     scram-sha-256

# Qualquer outro usuário/origem é recusado
host    all             all             all                     reject
HBA

docker exec "$container" psql -U otrs -d otrs -c "SELECT pg_reload_conf();"
echo "pg_hba.conf restrito aplicado no container $container"
