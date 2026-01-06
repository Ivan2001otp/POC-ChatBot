from fastapi import FastAPI
from app.api.endpoints import health 

app = FastAPI(title="POC")

app.include_router(health.router, tags=['health'])

@app.get("/")
def root():
    return {"message":"hi server."}