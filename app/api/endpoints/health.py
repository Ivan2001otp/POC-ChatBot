from fastapi import APIRouter, Query, HTTPException, Request
from pydantic_settings import BaseSettings
from datetime import datetime
import json

class Settings(BaseSettings):
    port:int = 8000
    verify_token:str="KWMXEK06dqdgg7PGZkOTmKxSSUZSH1MadZbA"

    class Config:
        env_file = ".env"

settings = Settings()

router = APIRouter()

@router.get("/health")
def health_check():
    return {"status":200, "message":"working"}


@router.get("/")
async def webhook_verify(
    mode : str = Query(None, alias='hub.mode'),
    challenge : str = Query(None, alias='hub.challenge'),
    token : str = Query(None, alias='hub.verify_token')
):
    
    print("mode is ", mode)
    print("challenge is ", challenge)
    print("token is ", token)
    print("verify_token value ", settings.verify_token)

    if mode == "subscribe" and token == settings.verify_token:
        print("WEBHOOK VERIFIED")
        return int(challenge)
    
    raise HTTPException(status_code=403, detail="Vefrification failed")

@router.post("/webhook")
async def webhook_recieve(request:Request):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n\nWebhook received {timestamp}\n")
    body = await request.json()
    print(json.dumps(body, indent = 2))
    return {"status":"ok"}