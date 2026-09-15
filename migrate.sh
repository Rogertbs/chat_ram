#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
test -f .env || { echo ".env não encontrado" >&2; exit 1; }

set -a
# .env é gerado localmente com valores hexadecimais.
source .env
set +a

docker compose --env-file .env -f mariadb/docker-compose.yml up -d --wait
docker compose --env-file .env -f postgres/docker-compose.yml up -d --wait

source_tables="$(docker compose --env-file .env -f mariadb/docker-compose.yml exec -T mariadb sh -ec 'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" mariadb -N -u root -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '\''otrs'\'' AND table_type = '\''BASE TABLE'\''"')"
[[ "$source_tables" == "195" ]] || { echo "Esperava 195 tabelas no MariaDB; encontrei $source_tables. Confira a restauração." >&2; exit 1; }

target_tables="$(docker compose --env-file .env -f postgres/docker-compose.yml exec -T postgres psql -U otrs -d otrs -Atc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'")"
[[ "$target_tables" == "0" ]] || { echo "PostgreSQL já contém $target_tables tabelas em public. Migração cancelada para proteger os dados." >&2; exit 1; }

load_file="$(mktemp /tmp/otrs-pgloader.XXXXXX.load)"
chmod 600 "$load_file"
trap 'rm -f "$load_file"' EXIT
python3 - "$load_file" <<'PY'
import os
import sys
from urllib.parse import quote

def esc(name):
    return quote(os.environ[name], safe="")

source = f"mysql://otrs:{esc('MARIADB_PASSWORD')}@mariadb:3306/otrs"
target = f"postgresql://otrs:{esc('POSTGRES_PASSWORD')}@postgres:5432/otrs"
command = f"""LOAD DATABASE
  FROM {source}
  INTO {target}
  WITH include no drop, create tables, create indexes, reset sequences,
       foreign keys, downcase identifiers, uniquify index names,
       workers = 2, concurrency = 1, prefetch rows = 1000,
       batch rows = 1000, batch size = 16MB
  ALTER TABLE NAMES MATCHING ~/./ SET SCHEMA 'public';
"""
with open(sys.argv[1], "w", encoding="utf-8") as f:
    f.write(command)
PY

echo "Migrando MariaDB → PostgreSQL com pgloader. O destino deve estar vazio."
docker run --rm --network otrs_migration -v "$load_file:/migration.load:ro" ghcr.io/dimitri/pgloader@sha256:a1d4a78e78a64e46cd3fc7dfc57d24eb91ffb1a5520f2b1f55631815e3658d6e pgloader /migration.load

python3 repair_schema.py
python3 preserve_text.py
python3 preserve_more_text.py
python3 verify.py
