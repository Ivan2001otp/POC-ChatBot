from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse
from datetime import datetime
import os
import json
import requests
from dotenv import load_dotenv
import re
from typing import List,Any,Optional,Dict
from dataclasses import dataclass, asdict

load_dotenv()

# constants
WHATSAPP_API_URL:str = "https://graph.facebook.com/v22.0/969259519597042/messages"
WHATSAPP_TOKEN:str = os.getenv("WHATSAPP_TOKEN","NO_TOKEN")# temp token or permanent token.


app = FastAPI(title="Facebook Webhook Server")
BASE_URL:str = "https://exp-man.m.frappe.cloud"
@dataclass
class Expense:
    name: str
    description: Optional[str]
    expense_amount: float
    employee: str

@dataclass
class ExpenseResponse:
    data: List[Expense]
    
    @classmethod
    def from_dict(cls, data_dict: Dict[str, Any]) -> 'ExpenseResponse':
        expenses = []

        print("data dict in from_dict():")
        print(data_dict)
        for item in data_dict.get("data", []):
            expense = Expense(
                name=item.get("name", ""),
                description=item.get("description"),
                expense_amount=item.get("expense_amount", 0.0),
                employee=item.get("employee", "")
            )
            expenses.append(expense)
        return cls(data=expenses)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "data": [asdict(expense) for expense in self.data]
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)
    
    def serialize(self) -> str:
        """Serialize to JSON string"""
        return self.to_json()
#---------------------------------------------------------------

#------------------------helper--------------------------------
def serialize_get_api_response(api_response:Dict[str,Any]):
    rsp = ExpenseResponse.from_dict(api_response)
    formatted_strings = []

    for idx, expense in enumerate(rsp.data, 1):
        expense_str = f"""Expense-{idx}
                Name: {expense.name}
                Description: {expense.description if expense.description else 'No description'}
                Expense Amount: {expense.expense_amount}
                Employee: {expense.employee}

                """
        formatted_strings.append(expense_str)
    
    return "".join(formatted_strings)


def print_json(data, indent=2):
    """Pretty print JSON"""
    print(json.dumps(data, indent=indent))


async def handle_add_expense(phone_number:str, message:str)->bool:
    return True

async def handle_get_user_expense(phone_number:str, message:str)->str :
    endpoint:str = "api/resource/CTExpense"
    headers:dict[str,str] = {
        "Authorization" : "token 9822fb1487561f6:8c3f8d54fd1cade"
    }

    params:dict[str,str] = {
        "fields":json.dumps(["name","description","expense_amount","employee"])
    }

    url:str = f"{BASE_URL}/{endpoint}"

    # print("requested url is ", url)
    try :
        response =  requests.get(url=url,  headers=headers, params=params)
        response.raise_for_status()
        formatted_response =  serialize_get_api_response(response.json())
        return formatted_response
        # return response.json()
    except requests.exceptions.RequestException as e :
        print(f"Error fetching data: {e}")
        return "Something went wrong. Please report this problem to us."
    except Exception as e :
        print(f"Something went wrong : {e}")
        return "Something went wrong. Please report this problem to us."

async def craft_message(phone_number:str, message:str) -> bool :
    regex_pattern : str =  r'\b(hi|hello)\b'
    bot_message:str = ''
    result  = False
    
    thanku_regex_pattern = r'\b(thank\s*you|thanks|thanx|thnx|thx|ty)\b'

    if re.search(regex_pattern, message, re.IGNORECASE):
        bot_message = """
            Hi there, Expense manager bot this side. How can I help you today.\n
            Type in the number to perform the desired task.\n\n

            1. Add expense
            2. Get user expense

            Note : Type in the number . For eg : 1 or 2.
        """
        result = await send_whatsapp_message(phone_number=phone_number, message=bot_message)

    elif re.search(thanku_regex_pattern, message, re.IGNORECASE):
        bot_message = """
           Your Welcome. 
           Thank you for using our service.
        """
        result = await send_whatsapp_message(phone_number=phone_number, message=bot_message)

    else :
    # check if the input is a valid numerical  choice or not.
        if message.isdigit() : 
            choice = int(message)

            if (choice > 2 or choice < 1) :
                bot_message = """
                    Invalid choice provided. \n
                    Kindly pick the valid choices again. 

                    1. Add expense 
                    2. Get user expense
                """
                result = await send_whatsapp_message(phone_number, "Invalid choice. Kindly choose either 1 or 2 as the choice.")
                return result
            

            match choice:
                case 1:
                    bot_message = await handle_add_expense(phone_number=phone_number, message="Add expense api is not working now. Try later.")
                    result = await send_whatsapp_message(phone_number=phone_number, message=bot_message)
                    return result
                case 2:
                    bot_message =  await handle_get_user_expense(phone_number=phone_number, message=message)
                    result = await send_whatsapp_message(phone_number=phone_number, message=bot_message)
                    return result
              
        else :
            bot_message = f"{message} is not a valid integer. It should be either 1 or 2. Kindly retry again."
            result = await send_whatsapp_message(phone_number=phone_number, message=bot_message)

    return result

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
        contact_name:str = body["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]
        phone_number:str = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
        message:str = body["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"]
        print(f"The text typed by client {contact_name} is - {message}")

        # want to make an api request here and send the status as success or failure.
        # your code goes here.
        api_result:str =  craft_message(phone_number=phone_number, message=message)
        # api_result = await send_whatsapp_message(phone_number, message)
        
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

@app.get("/testing_get_api")
async def get_response(request:Request):
    resp =  await  handle_get_user_expense("","")
    return resp

# For local development
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"\nStarting server on port {port}")
    print(f"Verify token: KWMXEK06dqdgg7PGZkOTmKxSSUZSH1MadZbA")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)