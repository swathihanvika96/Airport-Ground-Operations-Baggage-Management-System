#!/bin/sh
set -e
echo "Waiting for database..."
python - <<'PY'
import time
from sqlalchemy import create_engine, text
from app.core.config import settings
for attempt in range(30):
    try:
        with create_engine(settings.SQLALCHEMY_DATABASE_URI).connect() as c:
            c.execute(text("SELECT 1"))
        break
    except Exception as exc:
        print(f"  db not ready ({attempt + 1}/30): {exc.__class__.__name__}")
        time.sleep(2)
else:
    raise SystemExit("Database not reachable")
PY
echo "Running migrations..."
alembic upgrade head
if [ "${SEED_DEMO_DATA:-false}" = "true" ]; then
  python -m app.db.seed
fi
exec "$@"
