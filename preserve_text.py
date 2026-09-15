#!/usr/bin/env python3
"""Find changed article bodies and keep their exact MariaDB bytes in PostgreSQL."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV = ROOT / ".env"
MARIA = ROOT / "mariadb/docker-compose.yml"
POSTGRES = ROOT / "postgres/docker-compose.yml"


def base(compose, service):
    return ["docker", "compose", "--env-file", str(ENV), "-f", str(compose), "exec", "-T", service]


def maria_query(sql):
    return base(MARIA, "mariadb") + [
        "sh", "-ec",
        'MYSQL_PWD="$MARIADB_PASSWORD" exec mariadb -u otrs -D otrs --batch --raw --skip-column-names -e "$1"',
        "sh", sql,
    ]


def pg_query(sql):
    return base(POSTGRES, "postgres") + [
        "psql", "-U", "otrs", "-d", "otrs", "-At", "-F", "\t",
        "-v", "ON_ERROR_STOP=1", "-c", sql,
    ]


def run_pg(sql):
    subprocess.run(
        base(POSTGRES, "postgres") + ["psql", "-q", "-U", "otrs", "-d", "otrs", "-v", "ON_ERROR_STOP=1"],
        input=sql, text=True, check=True, stdout=subprocess.DEVNULL,
    )


def main():
    source_sql = "SELECT id,MD5(CAST(a_body AS BINARY)),IFNULL(OCTET_LENGTH(a_body),-1) FROM article_data_mime ORDER BY id"
    target_sql = "SELECT id,MD5(a_body),COALESCE(OCTET_LENGTH(a_body),-1) FROM public.article_data_mime ORDER BY id"
    source = subprocess.Popen(maria_query(source_sql), stdout=subprocess.PIPE, text=True)
    target = subprocess.Popen(pg_query(target_sql), stdout=subprocess.PIPE, text=True)
    changed = []
    seen = 0
    with source.stdout, target.stdout:
        for source_line, target_line in zip(source.stdout, target.stdout):
            a = source_line.rstrip("\n").split("\t")
            b = target_line.rstrip("\n").split("\t")
            if len(a) != 3 or len(b) != 3 or a[0] != b[0]:
                raise SystemExit(f"Linhas desalinhadas após {seen} registros")
            seen += 1
            source_hash = "" if a[1] == "NULL" else a[1].lower()
            target_hash = b[1].lower()
            if source_hash != target_hash or a[2] != b[2]:
                changed.append(int(a[0]))
    if source.wait() != 0 or target.wait() != 0:
        raise SystemExit("Falha ao ler article_data_mime")
    print(f"Corpos de mensagens auditados: {seen}; alterados na transferência: {len(changed)}", flush=True)
    if not changed:
        return

    run_pg("""
        CREATE TABLE IF NOT EXISTS public.otrs_migration_raw_article_body (
            article_data_mime_id bigint PRIMARY KEY REFERENCES public.article_data_mime(id),
            raw_body bytea NOT NULL,
            source_md5 text NOT NULL,
            source_bytes bigint NOT NULL
        );
    """)
    for article_id in changed:
        raw_sql = f"SELECT HEX(a_body),MD5(CAST(a_body AS BINARY)),OCTET_LENGTH(a_body) FROM article_data_mime WHERE id={article_id}"
        result = subprocess.run(maria_query(raw_sql), text=True, capture_output=True, check=True)
        parts = result.stdout.strip().split("\t")
        if len(parts) != 3:
            raise SystemExit(f"Não foi possível recuperar os bytes do corpo {article_id}")
        hex_body, md5, length = parts
        run_pg(
            "INSERT INTO public.otrs_migration_raw_article_body "
            "(article_data_mime_id,raw_body,source_md5,source_bytes) "
            f"VALUES ({article_id},decode('{hex_body}','hex'),'{md5}',{int(length)}) "
            "ON CONFLICT (article_data_mime_id) DO UPDATE SET "
            "raw_body=EXCLUDED.raw_body,source_md5=EXCLUDED.source_md5,source_bytes=EXCLUDED.source_bytes;\n"
        )
    print(f"Bytes originais preservados no PostgreSQL para {len(changed)} corpos de mensagens.")


if __name__ == "__main__":
    main()
