# PostgreSQL migration

Local dev uses SQLite with WAL (`backend/data_store/stock_picker.db`). Production should use PostgreSQL for concurrency and backups.

## 1. Provision database

```bash
createdb stock_picker
```

## 2. Configure environment

```env
APP_ENV=production
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/stock_picker
DATABASE_POOL_SIZE=10
JOB_QUEUE_BACKEND=db
```

Install driver:

```bash
pip install "psycopg[binary]>=3.1"
```

## 3. Create schema

Start the API once (runs `init_db()` → creates all tables on Postgres), or run:

```bash
cd backend && python -c "from data.cache import init_db; init_db()"
```

## 4. Copy existing SQLite data (optional)

```bash
export SQLITE_SOURCE_PATH=backend/data_store/stock_picker.db
export DATABASE_URL=postgresql+psycopg://...
python scripts/migrate_sqlite_to_postgres.py --dry-run
python scripts/migrate_sqlite_to_postgres.py
```

## 5. Background jobs

With `JOB_QUEUE_BACKEND=db` or `redis`, run a worker alongside the API:

```bash
python scripts/run_job_worker.py
```

Scheduler enqueues `daily_pipeline` and `quant_daily_jobs` instead of blocking the API process.

## Health check

`GET /health` reports `database_dialect`, `job_queue_backend`, `redis_connected`, and pinned `strategy_version` / `factor_model_version`.
