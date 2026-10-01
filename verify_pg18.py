#!/usr/bin/env python3
"""Compare the PostgreSQL 15 OTRS source with the PostgreSQL 18 copy."""

import argparse
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TARGET_DATABASE = "otrs"


def query(compose_file, service, sql, database="otrs"):
    result = subprocess.run(
        [
            "docker", "compose", "--env-file", str(ROOT / ".env"),
            "-f", str(ROOT / compose_file), "exec", "-T", service,
            "psql", "-U", "otrs", "-d", database, "-At", "-F", "|",
            "-v", "ON_ERROR_STOP=1",
        ],
        input=sql,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip().splitlines()


def source(sql):
    return query("postgres/docker-compose.yml", "postgres", sql)


def target(sql):
    return query("postgres18/docker-compose.yml", "postgres18", sql, TARGET_DATABASE)


def ident(name):
    return '"' + name.replace('"', '""') + '"'


def counts(rows):
    return {name: int(value) for name, value in (row.split("|", 1) for row in rows)}


def compare(label, sql):
    before, after = source(sql), target(sql)
    if before != after:
        raise RuntimeError(f"{label} diferem: origem={before[:12]}, destino={after[:12]}")
    print(f"{label}: conferidos ({len(before)} linhas)")
    return before


def main():
    global TARGET_DATABASE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-db", default="otrs", help="database in PostgreSQL 18")
    TARGET_DATABASE = parser.parse_args().target_db

    tables_sql = (
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' AND table_type='BASE TABLE' "
        "ORDER BY table_name;\n"
    )
    tables = compare("Tabelas", tables_sql)
    if len(tables) != 197:
        raise RuntimeError(f"Esperadas 197 tabelas, encontradas {len(tables)}")

    row_sql = "".join(
        f"SELECT '{name}', COUNT(*) FROM public.{ident(name)};\n"
        for name in tables
    )
    before_rows, after_rows = counts(source(row_sql)), counts(target(row_sql))
    differences = [(name, before_rows[name], after_rows.get(name)) for name in tables
                   if before_rows[name] != after_rows.get(name)]
    if differences:
        raise RuntimeError(f"Contagens divergentes: {differences[:20]}")
    print(f"Registros: {sum(before_rows.values()):,} em {len(tables)} tabelas".replace(",", "."))

    bytea_sql = (
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND udt_name='bytea' "
        "ORDER BY table_name, ordinal_position;\n"
    )
    bytea_columns = compare("Colunas bytea", bytea_sql)
    blob_sql = "".join(
        f"SELECT '{table}.{column}', COALESCE(SUM(OCTET_LENGTH({ident(column)})),0) "
        f"FROM public.{ident(table)};\n"
        for table, column in (row.split("|", 1) for row in bytea_columns)
    )
    before_blobs, after_blobs = counts(source(blob_sql)), counts(target(blob_sql))
    differences = [(name, value, after_blobs.get(name)) for name, value in before_blobs.items()
                   if value != after_blobs.get(name)]
    if differences:
        raise RuntimeError(f"Bytes binários divergentes: {differences[:20]}")
    print(f"Bytes binários: {sum(before_blobs.values()):,} em {len(bytea_columns)} colunas".replace(",", "."))

    compare(
        "Colunas e tipos",
        "SELECT c.relname, a.attname, format_type(a.atttypid,a.atttypmod), "
        "a.attnotnull, COALESCE(pg_get_expr(d.adbin,d.adrelid),'') "
        "FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum "
        "WHERE n.nspname='public' AND c.relkind IN ('r','p') "
        "AND a.attnum>0 AND NOT a.attisdropped "
        "ORDER BY c.relname,a.attnum;\n",
    )
    compare(
        "Restrições",
        "SELECT c.relname, x.conname, x.contype, pg_get_constraintdef(x.oid) "
        "FROM pg_constraint x JOIN pg_class c ON c.oid=x.conrelid "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' AND x.contype <> 'n' "
        "ORDER BY c.relname,x.conname;\n",
    )
    compare(
        "Índices",
        "SELECT tablename,indexname FROM pg_indexes WHERE schemaname='public' "
        "ORDER BY tablename,indexname;\n",
    )
    sequences = compare(
        "Sequências",
        "SELECT sequencename FROM pg_sequences WHERE schemaname='public' "
        "ORDER BY sequencename;\n",
    )
    if sequences:
        sequence_sql = "".join(
            f"SELECT '{name}', last_value, is_called FROM public.{ident(name)};\n"
            for name in sequences
        )
        compare("Estados das sequências", sequence_sql)

    saved_text = compare(
        "Textos originais preservados",
        "SELECT 'article_body', COUNT(*), COALESCE(SUM(OCTET_LENGTH(raw_body)),0), "
        "COUNT(*) FILTER (WHERE md5(raw_body)=source_md5 "
        "AND OCTET_LENGTH(raw_body)=source_bytes) "
        "FROM public.otrs_migration_raw_article_body "
        "UNION ALL "
        "SELECT 'other_text', COUNT(*), COALESCE(SUM(OCTET_LENGTH(raw_value)),0), "
        "COUNT(*) FILTER (WHERE md5(raw_value)=source_md5 "
        "AND OCTET_LENGTH(raw_value)=source_bytes) "
        "FROM public.otrs_migration_raw_text ORDER BY 1;\n",
    )
    expected_counts = {"article_body": 5, "other_text": 2}
    for row in saved_text:
        name, count, _, valid = row.split("|")
        if int(count) != expected_counts[name] or valid != count:
            raise RuntimeError(f"Bytes originais dos textos não conferem: {row}")
    print("Cópia PostgreSQL 15 → 18 validada.")


if __name__ == "__main__":
    main()
