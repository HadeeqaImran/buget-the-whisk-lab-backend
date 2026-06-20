# Budget Backend

FastAPI backend for the household budget calculator.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
docker compose up -d
uvicorn app.main:app --reload
```

The API runs at `http://localhost:8000`.

## Notes

- The app uses Postgres through SQLAlchemy.
- Tables are created at startup for a simple local development workflow.
- Update `DATABASE_URL` in `.env` if your Postgres credentials differ.
