# pgvector 0.8.6 on the PostgreSQL 18 Debian Trixie image.
FROM pgvector/pgvector:0.8.6-pg18-trixie AS textsearch-builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential git ca-certificates postgresql-server-dev-18 \
    && git clone --branch v1.4.0 --depth 1 \
       https://github.com/timescale/pg_textsearch.git /tmp/pg_textsearch \
    && make -C /tmp/pg_textsearch \
    && make -C /tmp/pg_textsearch install

FROM pgvector/pgvector:0.8.6-pg18-trixie

COPY --from=textsearch-builder /usr/lib/postgresql/18/lib/pg_textsearch.so /usr/lib/postgresql/18/lib/
COPY --from=textsearch-builder /usr/share/postgresql/18/extension/pg_textsearch.control /usr/share/postgresql/18/extension/
COPY --from=textsearch-builder /usr/share/postgresql/18/extension/pg_textsearch--*.sql /usr/share/postgresql/18/extension/
