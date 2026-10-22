# CareerTracker frontend

Small React interface for reviewing and mapping a user's pending skill suggestions. The existing FastAPI backend remains unchanged.

## Run locally

Start the API from the repository root in one terminal:

```powershell
python -m uvicorn app.main:app --reload
```

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite. The development server proxies `/api/*` to `http://127.0.0.1:8000/*`. To use another API host, set `CAREERTRACKER_API_URL` before starting Vite, for example:

```powershell
$env:CAREERTRACKER_API_URL = "http://127.0.0.1:8000"
npm run dev
```

The screen uses the existing `/auth/register`, `/auth/token`, `/auth/me`, `/skills`, `/skills/suggestions`, `/skills/suggestions/{id}/candidates`, and `PATCH /skills/suggestions/{id}` endpoints. It stores the access token in tab-scoped `sessionStorage`; signing out clears it. Mapping is confirmed by the user and remains scoped to that user's account.

Build a production bundle with `npm run build`.
