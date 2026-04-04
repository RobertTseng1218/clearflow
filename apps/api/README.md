# ClearFlow API v2 Scaffold

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

## Notes

- For local tests, SQLite is supported.
- For production, switch `DATABASE_URL` to PostgreSQL.
- `DEV_OAUTH_BYPASS=true` enables a safe local-only fake Google callback flow for development and tests.
