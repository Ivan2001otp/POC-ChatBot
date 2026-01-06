from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse
from datetime import datetime
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

# constants
WHATSAPP_API_URL:str = "https://graph.facebook.com/v22.0/969259519597042/messages"
WHATSAPP_TOKEN:str = os.getenv("WHATSAPP_TOKEN","NO_TOKEN")# temp token or permanent token.


app = FastAPI(title="Facebook Webhook Server")

def print_json(data, indent=2):
    """Pretty print JSON"""
    print(json.dumps(data, indent=indent))


async def send_whatsapp_message(phone_number:str, message:str)->bool:
    result:bool = False
    headers = {
        "Authorization":f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type":"application/json"
    }

    bot_message:str = f"Bot Echo : {message}"
    payload = {
        "messaging_product" : "whatsapp",
        "to":phone_number,
        "type":"text",
        "text":{
            "body":bot_message
        }
    }


    try :
        response = requests.post(
            WHATSAPP_API_URL,
            headers=headers,
            json=payload,
            timeout=10
        )

        response.raise_for_status()

        result = response.json()
        print(f"✅ Message sent successfully to {phone_number}")
        result = True
    
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to send message: {e}")
    
    except Exception as e : 
        print(f"❌ Unexpected error: {e}")
    
    return result

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
    api_result:bool = False

    try:
        body :dict = await request.json()
        print(print_json(body, 2))
        contact_name:str = body["entry"][0]["changes"]["value"]["contacts"][0]["profile"]["name"]
        phone_number:str = body["entry"][0]["changes"]["value"]["contacts"][0]["wa_id"]
        message:str = body["entry"][0]["changes"]["value"]["messages"][0]["text"]["body"]
        print(f"The text typed by client {contact_name} is - {message}")

        # want to make an api request here and send the status as success or failure.
        # your code goes here.
        api_result = await send_whatsapp_message(phone_number, message)
        
        # print_json(body)
    except Exception as e:
        print(f"Error parsing JSON: {e}")
        body = await request.body()
        print(f"Raw body: {body.decode()}")
    
    if api_result==False :
        return {"status":"failed"}
    
    return {"status": "success"}

# Health check endpoint for Render
@app.get("/health")
async def health_check():
    print("token from .env file is ", WHATSAPP_TOKEN)
    return {"status": "healthy", "service": "facebook-webhook"}


# For local development
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"\nStarting server on port {port}")
    print(f"Verify token: KWMXEK06dqdgg7PGZkOTmKxSSUZSH1MadZbA")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)