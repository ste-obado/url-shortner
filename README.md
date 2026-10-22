# Kata: URL shortener with analytics

Shorten links, pick custom names, set expiry dates, pause or delete links, and see clicks per day, devices and referrers.

**Stack:** FastAPI, SQLAlchemy 2, PostgreSQL, Redis (cache + sliding-window rate limiter), JWT auth, React + Vite.

## Run it locally

```bash
# backend (uses SQLite + in-memory cache if you set nothing)
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # edit SECRET_KEY
uvicorn app.main:app --reload                         # http://localhost:8000/docs

# frontend (new terminal)
cd frontend && npm install && npm run dev             # http://localhost:5173

# tests
cd backend && pytest
```

Or run backend + Postgres + Redis together: `docker compose up --build`.

## How it works

| Piece | What it does |
|---|---|
| `GET /{code}` | Looks in Redis first, falls back to the DB, redirects with 307, records the click in a background task |
| `POST /api/links` | Creates a link, rate limited to 10 per minute per user |
| `GET /api/stats/{code}` | Owner-only totals, 30-day series, devices, referrers |
| Login lockout | 5 wrong passwords locks that email for 5 minutes |

## Deploy

1. **Database:** create a free Postgres (Neon or Supabase) and copy its connection string.
2. **Backend:** push to GitHub, create a Web Service on Render (root directory `backend`, Docker). Set `DATABASE_URL`, `SECRET_KEY`, `BASE_URL` (your API URL), `CORS_ORIGINS` (your frontend URL), and `REDIS_URL` (Upstash free Redis, optional).
3. **Frontend:** import the repo on Vercel or Netlify (root directory `frontend`), set `VITE_API_URL` to your API URL.
4. **Own domain:** short domains make links look professional. Point it at the backend and set `BASE_URL` to it.
