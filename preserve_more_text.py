#!/usr/bin/env python3
"""Keep exact bytes for changed subject and search-index text values."""

import subprocess

from preserve_text import base, maria_query, pg_query, run_pg, MARIA, POSTGRES

FIELDS = [
    ("article_data_mime", "a_subject"),
    ("article_search_index", "article_value"),
]


def changed_ids(table, column):
    source_sql = f"SELECT id,MD5(CAST(`{column}` AS BINARY)),IFNULL(OCTET_LENGTH(`{column}`),-1) FROM `{table}` ORDER BY id"
    target_sql = f'SELECT id,MD5("{column}"),COALESCE(OCTET_LENGTH("{column}"),-1) FROM public."{table}" ORDER BY id'
    source = subprocess.Popen(maria_query(source_sql), stdout=subprocess.PIPE, text=True)
    target = subprocess.Popen(pg_query(target_sql), stdout=subprocess.PIPE, text=True)
    ids = []
    seen = 0
    with source.stdout, target.stdout:
        for source_line, target_line in zip(source.stdout, target.stdout):
            a = source_line.rstrip("\n").split("\t")
            b = target_line.rstrip("\n").split("\t")
            if len(a) != 3 or len(b) != 3 or a[0] != b[0]:
                raise SystemExit(f"Linhas desalinhadas em {table}.{column} após {seen} registros")
            seen += 1
            source_hash = "" if a[1] == "NULL" else a[1].lower()
            if source_hash != b[1].lower() or a[2] != b[2]:
                ids.append(int(a[0]))
    if source.wait() != 0 or target.wait() != 0:
        raise SystemExit(f"Falha ao ler {table}.{column}")
    print(f"{table}.{column}: {seen} registros auditados; {len(ids)} alterados", flush=True)
    return ids


def main():
    run_pg("""
        CREATE TABLE IF NOT EXISTS public.otrs_migration_raw_text (
            table_name text NOT NULL,
            column_name text NOT NULL,
            record_id bigint NOT NULL,
            raw_value bytea NOT NULL,
            source_md5 text NOT NULL,
            source_bytes bigint NOT NULL,
            PRIMARY KEY (table_name,column_name,record_id)
        );
    """)
    total = 0
    for table, column in FIELDS:
        for record_id in changed_ids(table, column):
            raw_sql = f"SELECT HEX(`{column}`),MD5(CAST(`{column}` AS BINARY)),OCTET_LENGTH(`{column}`) FROM `{table}` WHERE id={record_id}"
            result = subprocess.run(maria_query(raw_sql), text=True, capture_output=True, check=True)
            parts = result.stdout.strip().split("\t")
            if len(parts) != 3:
                raise SystemExit(f"Não foi possível recuperar {table}.{column}, id={record_id}")
            hex_value, md5, length = parts
            run_pg(
                "INSERT INTO public.otrs_migration_raw_text "
                "(table_name,column_name,record_id,raw_value,source_md5,source_bytes) "
                f"VALUES ('{table}','{column}',{record_id},decode('{hex_value}','hex'),'{md5}',{int(length)}) "
                "ON CONFLICT (table_name,column_name,record_id) DO UPDATE SET "
                "raw_value=EXCLUDED.raw_value,source_md5=EXCLUDED.source_md5,source_bytes=EXCLUDED.source_bytes;\n"
            )
            total += 1
    print(f"Bytes originais preservados para {total} valores adicionais.")


if __name__ == "__main__":
    main()
