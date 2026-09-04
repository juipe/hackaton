#!/bin/sh
# Container start-up: wait for Postgres, migrate, seed, serve.
set -eu

DB_WAIT_ATTEMPTS="${DB_WAIT_ATTEMPTS:-60}"
DB_WAIT_INTERVAL="${DB_WAIT_INTERVAL:-2}"

log() {
    echo "[skladchina] $*"
}

# Opens a real session with the URL and driver the API itself uses, so a passing
# probe proves more than an open port (all pg_isready would tell us, at the cost
# of an apt layer). connect_timeout keeps one attempt from blocking for minutes
# when the host swallows packets instead of refusing them, which is what makes
# the attempt count an actual bound.
probe_db() {
    python -c "import sqlalchemy as sa; from app.core.config import settings; u = settings.database_url; e = sa.create_engine(u, connect_args={} if u.startswith('sqlite') else {'connect_timeout': 5}); c = e.connect(); c.execute(sa.text('SELECT 1')); c.close()"
}

log "1/4 waiting for the database (${DB_WAIT_ATTEMPTS} attempts, ${DB_WAIT_INTERVAL}s apart)"
attempt=1
while ! probe_db 2>/dev/null; do
    if [ "${attempt}" -ge "${DB_WAIT_ATTEMPTS}" ]; then
        log "the database did not accept a connection after ${attempt} attempts - giving up"
        log "check DATABASE_URL and that the database service is running; last error:"
        probe_db || true
        exit 1
    fi
    attempt=$((attempt + 1))
    sleep "${DB_WAIT_INTERVAL}"
done
log "1/4 database is accepting connections (attempt ${attempt})"

log "2/4 applying migrations"
alembic upgrade head

# Seeding is the default because a reviewer running `docker compose up` has to
# land on a populated dashboard. The seed is idempotent, so restarts are safe.
case "$(printf '%s' "${SEED_ON_START-1}" | tr '[:upper:]' '[:lower:]')" in
    '' | 0 | false | no | off) run_seed=0 ;;
    *) run_seed=1 ;;
esac

if [ "${run_seed}" -eq 1 ]; then
    log "3/4 seeding demo data (set SEED_ON_START=0 to skip)"
    if ! python -m scripts.seed; then
        # Demo data is a convenience, not a prerequisite: a failure here must not
        # crash-loop the container and take the whole API away from the reviewer.
        log "3/4 seeding failed - starting anyway with whatever data is present"
    fi
else
    log "3/4 skipping demo data (SEED_ON_START=${SEED_ON_START-})"
fi

log "4/4 starting uvicorn on 0.0.0.0:8000"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
