from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse
from datetime import datetime
import os
import json
import requests
from dotenv import load_dotenv
import re
from typing import List,Any,Optional,Dict, Union
from dataclasses import dataclass, asdict


load_dotenv()

# constants
WHATSAPP_API_URL:str = "https://graph.facebook.com/v22.0/969259519597042/messages"
WHATSAPP_TOKEN:str = os.getenv("WHATSAPP_TOKEN","NO_TOKEN")# temp token or permanent token.


app = FastAPI(title="Facebook Webhook Server")
BASE_URL:str = "https://exp-man.m.frappe.cloud"

is_adding_expense_workflow_started:bool = False 
is_adding_expense_workflow_ended:bool = False 
add_expense_flag : dict[str, Any] = {
    "project":"",
    "employee":"",
    "expense_amount":0,
    "description":"",
    "expense_type":""
}

#-----------------------------------------------------------
# Code yet to be reviewed.
#-----------------------------------------------------------


expense_workflow_state = {}
current_expense_data = {}

async def craft_message_v2(phone_number: str, message: str) -> bool:
    print("executing craft message")

    regex_pattern: str = r'\b(hi|hello)\b'
    bot_message: str = ''
    result = False
    
    thanku_regex_pattern = r'\b(thank\s*you|thanks|thanx|thnx|thx|ty)\b'

    # Reset workflow if user says hi/hello
    if re.search(regex_pattern, message, re.IGNORECASE):
        # Reset workflow state for this user
        if phone_number in expense_workflow_state:
            del expense_workflow_state[phone_number]
        if phone_number in current_expense_data:
            del current_expense_data[phone_number]
       
        bot_message = """Hi there, Expense manager bot this side. \nHow can I help you today.\n
                        Type in the number to perform the desired task.\n\n
                        1. Add expense
                        2. Get user expense

                        Note : Type in the number. For eg: 1 or 2."""
        print("sending bot message via whatsapp cloud api")
        result = await send_whatsapp_message(phone_number=phone_number, message=bot_message)

    elif re.search(thanku_regex_pattern, message, re.IGNORECASE):
        print("user might have typed thank u")
        bot_message = """Your Welcome. 
Thank you for using our service."""
        result = await send_whatsapp_message(phone_number=phone_number, message=bot_message)

    else:
        # Check if user is in the middle of adding expense workflow
        if phone_number in expense_workflow_state:
            await handle_expense_workflow(phone_number, message)
            return True
        
        # If not in workflow, check for initial choice
        print("user has given choice")
        if message.isdigit():
            choice = int(message)

            if choice > 2 or choice < 1:
                bot_message = """Invalid choice provided. \n
Kindly pick the valid choices again. 

1. Add expense 
2. Get user expense"""
                result = await send_whatsapp_message(phone_number, bot_message)
                return result

            match choice:
                case 1:
                    # Start expense workflow
                    expense_workflow_state[phone_number] = {
                        'step': 'ask_project',
                        'data': {}
                    }
                    current_expense_data[phone_number] = {}
                    
                    bot_message = """Great! Let's add a new expense. I'll guide you step by step.

First, please provide the **Project Name** (must be an existing project):"""
                    result = await send_whatsapp_message(phone_number=phone_number, message=bot_message)
                    
                case 2:
                    print("user selected choice 2")
                    bot_message = await handle_get_user_expense(phone_number=phone_number, message=message)
                    result = await send_whatsapp_message(phone_number=phone_number, message=bot_message)
                    return result
        else:
            bot_message = f"{message} is not a valid integer. It should be either 1 or 2. Kindly retry again."
            result = await send_whatsapp_message(phone_number=phone_number, message=bot_message)

    return result

async def handle_expense_workflow(phone_number: str, user_input: str) -> bool:
    """Handle the step-by-step expense addition workflow"""
    if phone_number not in expense_workflow_state:
        return False
    
    workflow = expense_workflow_state[phone_number]
    step = workflow['step']
    
    bot_message = ""
    result = False
    
    try:
        match step:
            case 'ask_project':
                # Store project name
                if not user_input.strip():
                    bot_message = "Project name cannot be empty. Please provide a valid project name:"
                else:
                    current_expense_data[phone_number]['project'] = user_input.strip()
                    workflow['step'] = 'ask_employee'
                    bot_message = "Great! Now please provide the *Employee Email* (must be an existing employee email)"
                    
            case 'ask_employee':
                # Basic email validation
                if '@' not in user_input or '.' not in user_input:
                    bot_message = "Please provide a valid email address for the employee:"
                else:
                    current_expense_data[phone_number]['employee'] = user_input.strip()
                    workflow['step'] = 'ask_expense_amount'
                    bot_message = "Now, please provide the *Expense-Amount* (numbers only, e.g., 500):"
                    
            case 'ask_expense_amount':
                # Validate it's a number
                try:
                    amount = float(user_input)
                    if amount <= 0:
                        bot_message = "Expense amount must be greater than 0. Please enter a valid amount:"
                    else:
                        current_expense_data[phone_number]['expense_amount'] = amount
                        workflow['step'] = 'ask_expense_type'
                        bot_message = """Now, please select the *Expense Type*:
                                        1. Food
                                        2. Travel
                                        3. Office Supplies
                                        4. Equipment
                                        5. Other 

                                        Type the number corresponding to your choice (1-5):"""
                except ValueError:
                    bot_message = "Please enter a valid number for the expense amount (e.g., 500):"
                    
            case 'ask_expense_type':
                # Map number choices to expense types
                expense_type_map = {
                    '1': 'Food',
                    '2': 'Travel', 
                    '3': 'Office Supplies',
                    '4': 'Equipment',
                    '5': 'Other'
                }
                
                if user_input in expense_type_map:
                    current_expense_data[phone_number]['expense_type'] = expense_type_map[user_input]
                    workflow['step'] = 'ask_description'
                    bot_message = "Almost done! Please provide a *Description* for this expense (optional, type '*skip*' to skip):"
                else:
                    bot_message = """Please select a valid option (1-5):
                                    1. Food
                                    2. Travel
                                    3. Office Supplies
                                    4. Equipment
                                    5. Other"""
                    
            case 'ask_description':
                # Store description (allow empty/skip)
                if user_input.lower() == 'skip':
                    current_expense_data[phone_number]['description'] = "No description provided."
                else:
                    current_expense_data[phone_number]['description'] = user_input.strip()
                
                # All data collected, now submit to API
                bot_message = "Thank you! Collecting all your details...\n"
                result = await submit_expense_and_finalize(phone_number)
                return result
                
    except Exception as e:
        print(f"Error in expense workflow: {e}")
        bot_message = "Sorry, something went wrong. Let's start over.\n\nType 'hi' to begin again."
        # Clean up state
        if phone_number in expense_workflow_state:
            del expense_workflow_state[phone_number]
        if phone_number in current_expense_data:
            del current_expense_data[phone_number]
    
    # Send the bot message for current step
    if bot_message:
        await send_whatsapp_message(phone_number=phone_number, message=bot_message)
    
    return True

async def submit_expense_and_finalize(phone_number: str) -> bool:
    """Submit the collected expense data to API and send final response"""
    if phone_number not in current_expense_data:
        return False
    
    expense_data = current_expense_data[phone_number]
    
    # Prepare the data for API
    api_payload = {
        "project": expense_data.get('project', ''),
        "employee": expense_data.get('employee', ''),
        "expense_amount": expense_data.get('expense_amount', 0),
        "expense_type": expense_data.get('expense_type', 'Other'),
        "description": expense_data.get('description', '')
    }

    print("The api payload for add-expense is ", api_payload)
    
    bot_message = ""
    
    try:
        # Call your add expense API
        
        api_response = await add_expense_api(api_payload)
        
        if api_response.get('success', False):
            # Success case
            expense = api_response.get('data', {})
            bot_message = f"""✅ **Expense Added Successfully!**

                                    Here are the details:
                                    • Project: {expense.get('project', 'N/A')}
                                    • Employee: {expense.get('employee', 'N/A')}
                                    • Amount: ${expense.get('expense_amount', 0)}
                                    • Type: {expense.get('expense_type', 'N/A')}
                                    • Description: {expense.get('description', 'No description')}

                                    Your expense has been recorded. Type 'hi' to start over."""
        else:
            # Error case
            error_msg = api_response.get('message', 'Unknown error')
            bot_message = f"""❌ **Failed to Add Expense**

                                Error: {error_msg}

                                Please check your details and try again. Type 'hi' to restart."""
            
    except Exception as e:
        print(f"Error submitting expense: {e}")
        bot_message = f"""❌ **Error Processing Request**

                        Sorry, we encountered an error while processing your expense. Please try again later.

                        Type 'hi' to start over."""
    
    # Send final message
    result = await send_whatsapp_message(phone_number=phone_number, message=bot_message)
    
    # Clean up state
    if phone_number in expense_workflow_state:
        del expense_workflow_state[phone_number]
    if phone_number in current_expense_data:
        del current_expense_data[phone_number]
    
    return result

# Helper function to format expense type options
def get_expense_type_options():
    return """Please select an expense type:
1. Food
2. Travel  
3. Office Supplies
4. Equipment
5. Other"""

#------------------------------------------------------------
# This code needs to be reviewed
#------------------------------------------------------------


#-------------------------------------------------------------
@dataclass
class CTExpense:
    """Represents a CTExpense document"""
    name: str
    owner: str
    creation: str  # Could also use datetime if you parse it
    modified: str  # Could also use datetime if you parse it
    modified_by: str
    docstatus: int
    idx: int
    expense_amount: float
    expense_type: str
    description: Optional[str]
    employee: str
    project: str
    doctype: str
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CTExpense':
        """Create CTExpense from dictionary"""
        return cls(
            name=data.get("name", ""),
            owner=data.get("owner", ""),
            creation=data.get("creation", ""),
            modified=data.get("modified", ""),
            modified_by=data.get("modified_by", ""),
            docstatus=data.get("docstatus", 0),
            idx=data.get("idx", 0),
            expense_amount=data.get("expense_amount", 0.0),
            expense_type=data.get("expense_type", ""),
            description=data.get("description"),
            employee=data.get("employee", ""),
            project=data.get("project", ""),
            doctype=data.get("doctype", "CTExpense")
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2, default=str)

@dataclass 
class AddExpenseError :
    success:bool = False 
    message:str = "Failed to add expense" #default message
    error_details:Optional[str]=None 

    def to_dict(self)->Dict[str, Any]:
        return {
            "success":self.success ,
            "message":self.message,
            "error_details":self.error_details
        }

@dataclass
class AddExpenseResponse:
    """Wrapper for the API response"""
    data: CTExpense
    message:str = "Expense added to the system ✅"
    success:bool = True 
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AddExpenseResponse':
        """Create ExpenseResponse from API response dictionary"""
        return cls(
            data=CTExpense.from_dict(data.get("data", {}))
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary matching API response format"""
        return {
            "data": self.data.to_dict()
        }
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2, default=str)
    
    def serialize(self) -> str:
        """Serialize to string format for display"""
        expense = self.data
        return f"""
Expense Details:
Name: {expense.name}
Owner: {expense.owner}
Created: {expense.creation}
Modified: {expense.modified}
Modified By: {expense.modified_by}
Expense Amount: {expense.expense_amount}
Expense Type: {expense.expense_type}
Description: {expense.description if expense.description else 'No description'}
Employee: {expense.employee}
Project: {expense.project}
Document Type: {expense.doctype}
"""

#-------------------------------------------------------------
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


def parse_add_expense_response(response:requests.Response) -> Union[AddExpenseResponse, AddExpenseError]:
    try :
        status_code = response.status_code
        response_data = response.json() 

        if status_code == 200 :
            try :
                # extracting expense data.
                expense_data = response_data.get("data", {})
                if not expense_data :
                    return AddExpenseError(
                        success=False, 
                        message="No expense data found in response",
                        error_details="Response data is empty"
                    )
                
                expense = CTExpense.from_dict(expense_data)
                return AddExpenseResponse(
                    success=True, 
                    message=f"Expense '{expense.name}' added successfully ✅",
                    data=expense
                )
            except Exception as e : 
                return AddExpenseError(
                    success=False, 
                    message="Failed to parse expense data",
                    error_details=str(e)
                )
            
        elif status_code == 417 :
            error_message = "The expense details given (employee, project) to add expense is incorrect"

            return AddExpenseError(
                success=False,
                message=error_message,
                error_details=response_data.get("exception","The 'project' or 'employee' details provided is not present in our system")
            )
        
        else :
            error_message:str = f"Failed to add expense (Status: {status_code})"
            return AddExpenseError(
                success=False, 
                message=error_message,
                error_details=None
            ) 
    except json.JSONDecodeError as e:
        return AddExpenseError(
            success=False,
            message="Invalid response from server",
            error_details=f"Failed to parse JSON: {str(e)}"
        )
    except Exception as e :
        return AddExpenseError(
            success=False,
            message="Unexpected error processing response",
            error_details=str(e)
        )


async def add_expense_api(payload:dict[str, Any])->Dict[str, Any] : 
    endpoint : str = "api/resource/CTExpense"
    headers:dict[str,str] = {
        "Authorization" : "token 9822fb1487561f6:8c3f8d54fd1cade"
    }
    url :str = f"{BASE_URL}/{endpoint}"

    try :
        response =  requests.post(url=url,headers = headers,data=payload)
        response.raise_for_status()
        
        result = parse_add_expense_response(response)
        return result.to_dict()
        
    except requests.exceptions.RequestException as e :
        error_response = AddExpenseError(
            success=False, 
            message="Network error - failed to connect to expense system",
            error_details=str(e)
        )

    return error_response.to_dict() 

# @app.post("/test-add-expense")
# async def handle_add_expense(request:Request):
#     #phone_number:str, message:str
#     response =  await add_expense_api()
#     return response

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
    print("executing craft message")

    

    regex_pattern : str =  r'\b(hi|hello)\b'
    bot_message:str = ''
    result  = False
    
    thanku_regex_pattern = r'\b(thank\s*you|thanks|thanx|thnx|thx|ty)\b'

    if re.search(regex_pattern, message, re.IGNORECASE):
       
        bot_message = """
            Hi there, Expense manager bot this side. \n How can I help you today.\n
            Type in the number to perform the desired task.\n\n

            1. Add expense
            2. Get user expense

            Note : Type in the number . For eg : 1 or 2.
        """
        print("sending bot message via whatsapp cloud api")
        result = await send_whatsapp_message(phone_number=phone_number, message=bot_message)

    elif re.search(thanku_regex_pattern, message, re.IGNORECASE):
        print("user might have typed thank u")
        bot_message = """
           Your Welcome. 
           Thank you for using our service.
        """
        result = await send_whatsapp_message(phone_number=phone_number, message=bot_message)

    else :
    # check if the input is a valid numerical  choice or not.
        print("user has given choice")
        if message.isdigit() : 
            choice = int(message)

            if (choice > 2 or choice < 1) :
                bot_message = """
                    Invalid choice provided. \n
                    Kindly pick the valid choices again. 

                    1. Add expense 
                    2. Get user expense
                """
                result = await send_whatsapp_message(phone_number, bot_message)
                return result
            

            match choice:
                case 1:
                    if (is_adding_expense_workflow_started is False and is_adding_expense_workflow_ended is False):
                        is_adding_expense_workflow_started = True 

                        bot_message = """
                        To add expense kindly provide details like project, employee, expense_amount, description, expense_type.
                        """
               
                case 2:
                    print("user selected choice 2")
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

    bot_message:str = f"*Expense Manager Bot* : \n\n {message}"
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
    api_result: bool = False

    try:
        # Get raw body first
        raw_body = await request.body()
        body_str = raw_body.decode('utf-8')
        print(f"Raw body: {body_str}")
        
        # Parse JSON
        body: dict = json.loads(body_str)
        print_json(body, 2)
        
        contact_name: str = body["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]
        phone_number: str = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
        message: str = body["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"]

        api_result = await craft_message_v2(phone_number=phone_number, message=message)
        
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        print(f"Raw body that caused error: {body_str}")
        return {"status": "failed", "error": "Invalid JSON"}
        
    except KeyError as e:
        print(f"Missing expected field in JSON: {e}")
        print(f"Available keys: {list(body.keys()) if 'body' in locals() else 'No body parsed'}")
        return {"status": "failed", "error": f"Missing field: {e}"}
        
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "failed", "error": str(e)}
    
    if not api_result:
        print("response status is failed")
        return {"status": "failed"}
    
    print("response status is success")
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