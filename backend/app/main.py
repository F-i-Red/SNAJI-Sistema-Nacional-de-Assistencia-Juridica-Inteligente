
from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(
    title="SNAJI",
    version="9.0.0"
)

app.include_router(router)

@app.get("/")
async def root():
    return {
        "system": "SNAJI",
        "status": "online"
    }
