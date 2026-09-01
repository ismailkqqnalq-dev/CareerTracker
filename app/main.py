from fastapi import FastAPI

app = FastAPI(title="CareerTracker")


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "CareerTracker is running."}
