FROM pgvector/pgvector:pg16

ENV POSTGRES_DB=vault_db \
    POSTGRES_USER=vault_user \
    POSTGRES_PASSWORD=vault_secure_password

EXPOSE 5432

HEALTHCHECK --interval=5s --timeout=5s --start-period=5s --retries=5 \
    CMD pg_isready -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" || exit 1
