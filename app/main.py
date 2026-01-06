from fastapi import FastAPI
from app.api.endpoints import health 
import os 

app = FastAPI(title="POC")

app.include_router(health.router, tags=['health'])

# @app.get("/")
# def root():
#     return {"message":"hi server."}


if __name__ == "__main__" :
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app",host="0.0.0.0",port=port,reload=False)