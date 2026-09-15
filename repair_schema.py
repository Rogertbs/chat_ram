#!/usr/bin/env python3
"""Recreate MariaDB primary keys, indexes and foreign keys in PostgreSQL."""

import hashlib
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(service, sql, capture=True):
    compose = ROOT / ("mariadb/docker-compose.yml" if service == "mariadb" else "postgres/docker-compose.yml")
    base = ["docker", "compose", "--env-file", str(ROOT / ".env"), "-f", str(compose), "exec", "-T", service]
    if service == "mariadb":
        command = ["sh", "-ec", 'MYSQL_PWD="$MARIADB_PASSWORD" exec mariadb -u otrs -D otrs --batch --raw --skip-column-names']
    else:
        command = ["psql", "-U", "otrs", "-d", "otrs", "-At", "-F", "\t", "-v", "ON_ERROR_STOP=1"]
    result = subprocess.run(base + command, input=sql, text=True, capture_output=capture, check=True)
    return result.stdout.strip().splitlines() if capture else []


def ident(name):
    return '"' + name.replace('"', '""') + '"'


def short_name(prefix, table, name):
    raw = f"{prefix}_{table}_{name}".lower()
    if len(raw.encode()) <= 63:
        return raw
    return raw[:53] + "_" + hashlib.sha1(raw.encode()).hexdigest()[:8]


def main():
    rows = run("mariadb", """
        SELECT table_name,index_name,non_unique,seq_in_index,column_name,IFNULL(sub_part,'')
        FROM information_schema.statistics
        WHERE table_schema='otrs'
        ORDER BY table_name,index_name,seq_in_index;
    """)
    grouped = defaultdict(list)
    for row in rows:
        table, index, non_unique, sequence, column, prefix = row.split("\t")
        grouped[(table, index, int(non_unique))].append((int(sequence), column, prefix))

    existing_pks = set(run("postgres", """
        SELECT c.relname FROM pg_constraint x
        JOIN pg_class c ON c.oid=x.conrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND x.contype='p';
    """))
    ddl = []
    primary = []
    unique = []
    ordinary = []
    for (table, index, non_unique), items in grouped.items():
        items.sort()
        expressions = []
        for _, column, prefix in items:
            col = ident(column)
            expressions.append(f"left({col},{int(prefix)})" if prefix else col)
        cols = ", ".join(expressions)
        if index == "PRIMARY":
            if table not in existing_pks:
                primary.append(f"ALTER TABLE public.{ident(table)} ADD CONSTRAINT {ident(short_name('pk', table, 'id'))} PRIMARY KEY ({cols});")
        else:
            name = ident(short_name("idx", table, index))
            statement = f"CREATE {'UNIQUE ' if non_unique == 0 else ''}INDEX IF NOT EXISTS {name} ON public.{ident(table)} ({cols});"
            (unique if non_unique == 0 else ordinary).append(statement)

    fk_rows = run("mariadb", """
        SELECT k.table_name,k.constraint_name,k.ordinal_position,k.column_name,
               k.referenced_table_name,k.referenced_column_name,r.update_rule,r.delete_rule
        FROM information_schema.key_column_usage k
        JOIN information_schema.referential_constraints r
          ON r.constraint_schema=k.constraint_schema AND r.constraint_name=k.constraint_name
        WHERE k.constraint_schema='otrs' AND k.referenced_table_name IS NOT NULL
        ORDER BY k.table_name,k.constraint_name,k.ordinal_position;
    """)
    fk_group = defaultdict(list)
    for row in fk_rows:
        table, name, position, column, target, target_col, update_rule, delete_rule = row.split("\t")
        fk_group[(table, name, target, update_rule, delete_rule)].append((int(position), column, target_col))
    existing_fks = set(run("postgres", """
        SELECT c.relname || '.' || x.conname FROM pg_constraint x
        JOIN pg_class c ON c.oid=x.conrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND x.contype='f';
    """))
    foreign = []
    for (table, name, target, update_rule, delete_rule), items in fk_group.items():
        key_name = short_name("fk", table, name)
        if f"{table}.{key_name}" in existing_fks:
            continue
        items.sort()
        cols = ", ".join(ident(column) for _, column, _ in items)
        refs = ", ".join(ident(target_col) for _, _, target_col in items)
        # MariaDB reports RESTRICT, NO ACTION, CASCADE, SET NULL or SET DEFAULT.
        foreign.append(
            f"ALTER TABLE public.{ident(table)} ADD CONSTRAINT {ident(key_name)} "
            f"FOREIGN KEY ({cols}) REFERENCES public.{ident(target)} ({refs}) "
            f"ON UPDATE {update_rule} ON DELETE {delete_rule};"
        )

    ddl = primary + unique + ordinary + foreign
    print(f"Criando {len(primary)} chaves primárias, {len(unique)} índices únicos, {len(ordinary)} índices e {len(foreign)} chaves estrangeiras.", flush=True)
    if ddl:
        run("postgres", "\n".join(ddl) + "\n", capture=False)
    print("Índices e chaves criados.")


if __name__ == "__main__":
    main()
