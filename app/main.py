from fastapi import FastAPI
from app.routes.opportunity_routes import router as opportunity_router
app = FastAPI(title="CareerTracker")
app.include_router(opportunity_router)

@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "CareerTracker is running."}
