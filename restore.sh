#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
test -s BackpOtrs.sql || { echo "BackpOtrs.sql não encontrado ou vazio" >&2; exit 1; }
test -f .env || { echo ".env não encontrado" >&2; exit 1; }

docker compose --env-file .env -f mariadb/docker-compose.yml up -d --wait

table_count="$(docker compose --env-file .env -f mariadb/docker-compose.yml exec -T mariadb sh -ec 'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" mariadb -N -u root -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '\''otrs'\'' AND table_type = '\''BASE TABLE'\''"')"
if [[ "$table_count" != "0" ]]; then
  echo "O banco MariaDB já contém $table_count tabelas. Importação cancelada para evitar sobrescrever dados." >&2
  exit 1
fi

echo "Importando BackpOtrs.sql (2,5 GB) no MariaDB. Isto pode demorar."
docker compose --env-file .env -f mariadb/docker-compose.yml exec -T mariadb sh -ec 'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" mariadb --binary-mode -u root otrs' < BackpOtrs.sql

docker compose --env-file .env -f mariadb/docker-compose.yml exec -T mariadb sh -ec 'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" mariadb -N -u root -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '\''otrs'\'' AND table_type = '\''BASE TABLE'\''"'
