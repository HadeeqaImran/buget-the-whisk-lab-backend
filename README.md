# Budget Backend

FastAPI backend for the household budget calculator.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

The API runs at `http://localhost:8000`.

## Database

Create a local Postgres database that matches `.env.example`:

```bash
createdb budget_db
createuser budget
psql -d budget_db -c "ALTER USER budget WITH PASSWORD 'budget';"
psql -d budget_db -c "GRANT ALL PRIVILEGES ON DATABASE budget_db TO budget;"
```

If your local Postgres credentials are different, update `DATABASE_URL` in `.env`.

## Notes

- The app uses Postgres through SQLAlchemy.
- Tables are created at startup for a simple local development workflow.
- Update `DATABASE_URL` in `.env` if your Postgres credentials differ.
