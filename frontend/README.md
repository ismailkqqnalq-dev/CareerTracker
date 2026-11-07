# CareerTracker frontend

Authenticated React web interface for the core CareerTracker CRM: overview, opportunities, contacts, tasks, activities, profile skills, skill matching, suggestions, job-text analysis, OCR, and monthly application analytics. It uses the existing FastAPI API; the backend and database schema are unchanged by frontend work.

## Run locally

Start the API from the repository root in one terminal:

```powershell
python -m uvicorn app.main:app --reload
```

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open the local URL printed by Vite. The development server proxies `/api/*` to `http://127.0.0.1:8000/*`. To use another API host, set `CAREERTRACKER_API_URL` before starting Vite, for example:

```powershell
$env:CAREERTRACKER_API_URL = "http://127.0.0.1:8000"
npm run dev
```

CRM lists use the existing paginated endpoints and show 50 records per page. Create, update, and delete actions stay scoped to the signed-in user's backend permissions. Deleting an opportunity warns that its linked contacts, tasks, and activities are deleted by the current cascade behavior.

The access token is stored in tab-scoped `sessionStorage`; signing out or receiving HTTP 401 clears the session. OCR and job-analysis results are not saved by the API. Skill mappings require user confirmation and remain scoped to that user's account.

Build a production bundle with `npm run build`.
