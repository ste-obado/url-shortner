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

## M-Pesa plans

| Plan | Price | Links |
|---|---|---|
| Free | KES 0 | 10 |
| Pro | KES 500 / 30 days | 500 |
| Enterprise | KES 1,000 / 30 days | unlimited |

Prices live in `backend/app/plans.py`. The amount is always set by the server, never by the browser.

**Test it in the Daraja sandbox**
1. Create an app at developer.safaricom.co.ke, enable *M-Pesa Sandbox*, copy the consumer key/secret and the *Lipa Na M-Pesa Online* test passkey.
2. Run `ngrok http 8000` and put the https URL in `MPESA_CALLBACK_BASE_URL` (Safaricom must be able to reach your callback).
3. Fill the `MPESA_*` values in `backend/.env`, restart the API, sign in, press the plan badge, choose a plan, and pay with the sandbox test phone number from the Daraja simulator.
4. No credentials yet? Set `MPESA_ENV=mock` to see the whole UI flow with fake payments. **Never use mock mode on a public server.**

**Going live:** get a Paybill or Till from Safaricom, set `MPESA_ENV=production`, use your real shortcode and passkey, and `MPESA_TRANSACTION_TYPE=CustomerBuyGoodsOnline` if it's a Till.

**Safety rules in the code** (all covered by tests): one pending payment per user (database-enforced), replayed callbacks never grant days twice, wrong-amount or reused-receipt payments go to `review` instead of activating, a missed callback is recovered by querying Daraja, and a stale attempt is checked before the user is asked to pay again. Payments in `review` need a manual look: `SELECT * FROM payments WHERE status = 'review';`

## Deploy

1. **Database:** create a free Postgres (Neon or Supabase) and copy its connection string.
2. **Backend:** push to GitHub, create a Web Service on Render (root directory `backend`, Docker). Set `DATABASE_URL`, `SECRET_KEY`, `BASE_URL` (your API URL), `CORS_ORIGINS` (your frontend URL), and `REDIS_URL` (Upstash free Redis, optional).
3. **Frontend:** import the repo on Vercel or Netlify (root directory `frontend`), set `VITE_API_URL` to your API URL.
4. **Own domain:** short domains make links look professional. Point it at the backend and set `BASE_URL` to it.
