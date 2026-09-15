#!/usr/bin/env python3
"""Compare UTF-8 byte totals for every MariaDB text column."""

from collections import defaultdict

from verify import maria, pg, mysql_ident, pg_ident


def main():
    rows = maria(
        "SELECT table_name,column_name FROM information_schema.columns "
        "WHERE table_schema='otrs' AND data_type IN ('varchar','text','mediumtext','longtext') "
        "ORDER BY table_name,ordinal_position;\n"
    )
    grouped = defaultdict(list)
    for row in rows:
        table, column = row.split("\t")
        grouped[table].append(column)

    source_sql = []
    target_sql = []
    for table, columns in grouped.items():
        source_parts = ",".join(f"COALESCE(SUM(OCTET_LENGTH({mysql_ident(c)})),0)" for c in columns)
        target_parts = ",".join(f"COALESCE(SUM(OCTET_LENGTH({pg_ident(c)})),0)" for c in columns)
        source_sql.append(f"SELECT '{table}',{source_parts} FROM {mysql_ident(table)};\n")
        target_sql.append(f"SELECT '{table}',{target_parts} FROM {pg_ident(table)};\n")

    source = {line.split("\t")[0]: line.split("\t")[1:] for line in maria("".join(source_sql))}
    target = {line.split("|")[0]: line.split("|")[1:] for line in pg("".join(target_sql))}
    differences = []
    for table, columns in grouped.items():
        a = source[table]
        b = target[table]
        if len(a) != len(columns) or len(b) != len(columns):
            raise SystemExit(f"Resultado incompleto para {table}")
        for column, before, after in zip(columns, a, b):
            if before != after:
                differences.append((table, column, int(before), int(after)))

    print(f"Colunas de texto verificadas: {sum(map(len, grouped.values()))}; diferenças: {len(differences)}")
    for table, column, before, after in differences:
        print(f"DIFERENÇA {table}.{column}: MariaDB={before} bytes; PostgreSQL={after} bytes")
    if differences:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
