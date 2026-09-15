#!/usr/bin/env python3
"""Compare exact row counts and binary byte totals in both migration databases."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def call(compose_file, service, command, sql):
    result = subprocess.run(
        [
            "docker", "compose", "--env-file", str(ROOT / ".env"),
            "-f", str(ROOT / compose_file), "exec", "-T", service,
            *command,
        ],
        input=sql,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip().splitlines()


def maria(sql):
    return call(
        "mariadb/docker-compose.yml", "mariadb",
        ["sh", "-ec", 'MYSQL_PWD="$MARIADB_PASSWORD" exec mariadb -u otrs -D otrs --batch --raw --skip-column-names'],
        sql,
    )


def pg(sql):
    return call(
        "postgres/docker-compose.yml", "postgres",
        ["psql", "-U", "otrs", "-d", "otrs", "-At", "-F", "|", "-v", "ON_ERROR_STOP=1"],
        sql,
    )


def mysql_ident(name):
    return "`" + name.replace("`", "``") + "`"


def pg_ident(name):
    return '"' + name.replace('"', '""') + '"'


def parse(lines, separator):
    return {parts[0]: int(parts[1]) for line in lines if len(parts := line.split(separator)) == 2}


def main():
    tables = maria("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE';\n")
    names = [line.split("\t", 1)[0] for line in tables]
    if len(names) != 195:
        raise SystemExit(f"MariaDB contém {len(names)} tabelas; esperado: 195")

    target_names = set(pg(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' AND table_type='BASE TABLE' "
        "AND table_name NOT LIKE 'otrs_migration_%' ORDER BY table_name;\n"
    ))
    if target_names != set(names):
        raise SystemExit(f"Diferença nas tabelas: ausentes={sorted(set(names)-target_names)}, extras={sorted(target_names-set(names))}")

    source_sql = "".join(f"SELECT '{name}', COUNT(*) FROM {mysql_ident(name)};\n" for name in names)
    target_sql = "".join(f"SELECT '{name}', COUNT(*) FROM {pg_ident(name)};\n" for name in names)
    source = parse(maria(source_sql), "\t")
    target = parse(pg(target_sql), "|")
    mismatches = [(name, source.get(name), target.get(name)) for name in names if source.get(name) != target.get(name)]
    print(f"Tabelas verificadas: {len(names)}; registros MariaDB: {sum(source.values())}; PostgreSQL: {sum(target.values())}")
    for name, before, after in mismatches:
        print(f"DIFERENÇA de registros em {name}: MariaDB={before}, PostgreSQL={after}")

    blob_columns = maria(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema='otrs' AND data_type IN ('blob','mediumblob','longblob') "
        "ORDER BY table_name, ordinal_position;\n"
    )
    columns = [line.split("\t", 1) for line in blob_columns]
    source_blob_sql = "".join(
        f"SELECT '{table}.{column}', COALESCE(SUM(OCTET_LENGTH({mysql_ident(column)})),0) FROM {mysql_ident(table)};\n"
        for table, column in columns
    )
    target_blob_sql = "".join(
        f"SELECT '{table}.{column}', COALESCE(SUM(OCTET_LENGTH({pg_ident(column)})),0) FROM {pg_ident(table)};\n"
        for table, column in columns
    )
    source_blobs = parse(maria(source_blob_sql), "\t")
    target_blobs = parse(pg(target_blob_sql), "|")
    blob_mismatches = [(name, total, target_blobs.get(name)) for name, total in source_blobs.items() if total != target_blobs.get(name)]
    print(f"Colunas binárias verificadas: {len(columns)}; bytes MariaDB: {sum(source_blobs.values())}; PostgreSQL: {sum(target_blobs.values())}")
    for name, before, after in blob_mismatches:
        print(f"DIFERENÇA de bytes em {name}: MariaDB={before}, PostgreSQL={after}")

    source_constraints = dict(
        line.split("\t") for line in maria(
            "SELECT constraint_type,COUNT(*) FROM information_schema.table_constraints "
            "WHERE table_schema='otrs' GROUP BY constraint_type;\n"
        )
    )
    target_constraints = dict(
        line.split("|") for line in pg(
            "SELECT CASE x.contype WHEN 'p' THEN 'PRIMARY KEY' WHEN 'f' THEN 'FOREIGN KEY' END,COUNT(*) "
            "FROM pg_constraint x JOIN pg_class c ON c.oid=x.conrelid "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relname NOT LIKE 'otrs_migration_%' "
            "AND x.contype IN ('p','f') GROUP BY x.contype;\n"
        )
    )
    source_index_count = int(maria(
        "SELECT COUNT(*) FROM (SELECT table_name,index_name FROM information_schema.statistics "
        "WHERE table_schema='otrs' GROUP BY table_name,index_name) AS x;\n"
    )[0])
    target_index_count = int(pg(
        "SELECT COUNT(*) FROM pg_indexes WHERE schemaname='public' "
        "AND tablename NOT LIKE 'otrs_migration_%';\n"
    )[0])
    print(f"Chaves primárias: MariaDB={source_constraints.get('PRIMARY KEY',0)}, PostgreSQL={target_constraints.get('PRIMARY KEY',0)}")
    print(f"Chaves estrangeiras: MariaDB={source_constraints.get('FOREIGN KEY',0)}, PostgreSQL={target_constraints.get('FOREIGN KEY',0)}")
    print(f"Índices: MariaDB={source_index_count}, PostgreSQL={target_index_count}")

    raw_body = pg(
        "SELECT COUNT(*),COALESCE(SUM(OCTET_LENGTH(raw_body)),0),"
        "COALESCE(SUM(source_bytes),0),"
        "COUNT(*) FILTER (WHERE md5(raw_body)=source_md5 AND OCTET_LENGTH(raw_body)=source_bytes) "
        "FROM public.otrs_migration_raw_article_body;\n"
    )[0].split("|")
    raw_other = pg(
        "SELECT COUNT(*),COALESCE(SUM(OCTET_LENGTH(raw_value)),0),"
        "COALESCE(SUM(source_bytes),0),"
        "COUNT(*) FILTER (WHERE md5(raw_value)=source_md5 AND OCTET_LENGTH(raw_value)=source_bytes) "
        "FROM public.otrs_migration_raw_text;\n"
    )[0].split("|")
    print(f"Valores de texto com bytes originais preservados: corpos={raw_body[0]}, outros={raw_other[0]}")

    schema_bad = (
        int(source_constraints.get('PRIMARY KEY', 0)) != int(target_constraints.get('PRIMARY KEY', 0))
        or int(source_constraints.get('FOREIGN KEY', 0)) != int(target_constraints.get('FOREIGN KEY', 0))
        or source_index_count != target_index_count
    )
    raw_bad = (
        raw_body[0] != "5" or raw_body[1] != raw_body[2] or raw_body[0] != raw_body[3]
        or raw_other[0] != "2" or raw_other[1] != raw_other[2] or raw_other[0] != raw_other[3]
    )
    if mismatches or blob_mismatches or schema_bad or raw_bad:
        raise SystemExit("Migração NÃO validada: há diferenças")
    print("Contagens, dados binários, chaves e índices conferidos. Bytes originais dos sete textos alterados preservados.")


if __name__ == "__main__":
    main()
