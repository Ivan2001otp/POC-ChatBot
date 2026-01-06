from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse
from datetime import datetime
import os
import json

app = FastAPI(title="Facebook Webhook Server")

def print_json(data, indent=2):
    """Pretty print JSON"""
    print(json.dumps(data, indent=indent))

# GET endpoint for webhook verification
@app.get("/", response_class=PlainTextResponse)
async def verify_webhook(
    mode: str = Query(None, alias="hub.mode"),
    challenge: str = Query(None, alias="hub.challenge"),
    token: str = Query(None, alias="hub.verify_token")
):
    print(f"Verification attempt: mode={mode}, token={token}")
    
    if mode == "subscribe" and token == "KWMXEK06dqdgg7PGZkOTmKxSSUZSH1MadZbA":
        print("WEBHOOK VERIFIED")
        return challenge  # Facebook expects the challenge string as response
    else:
        print("VERIFICATION FAILED")
        raise HTTPException(status_code=403, detail="Verification failed")

# POST endpoint for receiving webhook events
@app.post("/")
async def receive_webhook(request: Request):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*50}")
    print(f"Webhook received {timestamp}")
    print(f"{'='*50}\n")
    
    try:
        body = await request.json()
        print_json(body)
    except Exception as e:
        print(f"Error parsing JSON: {e}")
        body = await request.body()
        print(f"Raw body: {body.decode()}")
    
    return {"status": "ok"}

# Health check endpoint for Render
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "facebook-webhook"}

# For local development
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"\nStarting server on port {port}")
    print(f"Verify token: KWMXEK06dqdgg7PGZkOTmKxSSUZSH1MadZbA")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)