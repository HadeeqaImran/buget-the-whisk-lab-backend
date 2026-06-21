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
- Registration creates a default family for the user.
- Budget categories and entries are scoped to the active family.
- Change `SECRET_KEY` in `.env` before using the app outside local development.

## Deploy to Render

This backend includes a `render.yaml` Blueprint for Render. It creates:

- A Python web service named `budget-board-api`
- A Render Postgres database named `budget-board-db`
- A `/health` health check
- A generated `SECRET_KEY`

### Blueprint deploy

1. Push this backend repo to GitHub.
2. In Render, choose **New +** → **Blueprint**.
3. Connect the GitHub repo for this backend.
4. Render will detect `render.yaml`.
5. Set the `CORS_ORIGINS` environment variable when Render prompts you.

Use your frontend URL for production CORS:

```txt
https://your-frontend-domain.com
```

For local frontend testing against the deployed API, include localhost too:

```txt
http://localhost:5173,http://127.0.0.1:5173,https://your-frontend-domain.com
```

After deploy, your API will be available at the Render service URL, for example:

```txt
https://budget-board-api.onrender.com
```

Update the frontend environment variable to point at it:

```txt
VITE_API_URL=https://budget-board-api.onrender.com
```

### Manual deploy settings

If you do not use the Blueprint, create a Render **Web Service** with:

```txt
Runtime: Python
Build Command: pip install -r requirements.txt
Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
Health Check Path: /health
```

Then create a Render Postgres database and add these web service environment variables:

```txt
DATABASE_URL=<Render Postgres connection string>
CORS_ORIGINS=https://your-frontend-domain.com
SECRET_KEY=<long random secret>
ACCESS_TOKEN_EXPIRE_MINUTES=10080
PYTHON_VERSION=3.13.5
```
