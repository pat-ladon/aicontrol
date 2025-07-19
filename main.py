# --- START OF REVISED main.py (for v0.1 - Step 1) ---

import os
from dotenv import load_dotenv
import csv
from typing import List, Optional

from fastapi import FastAPI, Request, Form, HTTPException, Response
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# --- FastAPI App Setup ---
load_dotenv()
app = FastAPI()
DEMO_PASSCODE = os.getenv("DEMO_PASSCODE")
SECRET_KEY = os.getenv("SECRET_KEY") 
COOKIE_NAME = "demo_session"

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Middleware for Authentication ---
# This part is fine to keep as it controls access to the app.
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in ["/login", "/favicon.ico"] or request.url.path.startswith("/static"):
            return await call_next(request)

        passcode_in_cookie = request.cookies.get(COOKIE_NAME)
        if passcode_in_cookie and passcode_in_cookie == DEMO_PASSCODE:
            return await call_next(request)

        return templates.TemplateResponse("login_dialog.html", {"request": request, "error": None})
    
app.add_middleware(AuthMiddleware)

# --- Login Endpoint ---
@app.post("/login")
async def login(request: Request, passcode: str = Form(...)):
    if passcode == DEMO_PASSCODE:
        response = Response(headers={"HX-Refresh": "true"})
        response.set_cookie(key=COOKIE_NAME, value=passcode, httponly=True, max_age=86400)
        return response
    else:
        return templates.TemplateResponse(
            "login_dialog.html",
            {"request": request, "error": "Invalid passcode. Please try again."}
        )

# --- Data Model & Loading ---
class Control(BaseModel):
    id: str
    name: str
    risk_id: str
    status: str
    owner: str
    risk_text: str
    control_text: str
    # Removed AI-related fields like 'suggestions' and 'assessment_document' for now

controls: List[Control] = []

def load_controls_from_csv():
    """Loads control data from controls.csv into the in-memory list."""
    try:
        with open("controls.csv", mode='r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            for row in reader:
                # The Control model will only populate the fields it knows about.
                controls.append(Control(**row))
        print(f"Loaded {len(controls)} controls from controls.csv")
    except FileNotFoundError:
        print("Error: controls.csv not found. No controls will be loaded.")

# Load data on startup
load_controls_from_csv()

# --- Helper Function to find a control ---
def find_control_by_id(control_id: str) -> Optional[Control]:
    return next((c for c in controls if c.id == control_id), None)

# --- Core Endpoints ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serves the main index page with the list of all controls."""
    return templates.TemplateResponse("index.html", {"request": request, "controls": controls})

@app.post("/search", response_class=HTMLResponse)
async def search_controls(request: Request, query: str = Form(...)):
    """Filters controls and returns the updated list as an HTML fragment."""
    search_term = query.lower().strip()
    if not search_term:
        filtered_controls = controls
    else:
        filtered_controls = [
            c for c in controls if
            search_term in c.name.lower() or
            search_term in c.risk_id.lower() or
            search_term in c.owner.lower() or
            search_term in c.status.lower()
        ]
    return templates.TemplateResponse(
        "partials/control_list.html", 
        {"request": request, "controls": filtered_controls}
    )

@app.get("/controls/{control_id}", response_class=HTMLResponse)
async def get_control(request: Request, control_id: str):
    """
    Serves the control detail view. This is the endpoint that renders our new
    structured assessment form.
    """
    control = find_control_by_id(control_id)
    if not control:
        raise HTTPException(status_code=404, detail="Control not found")
    
    # This endpoint now renders the simplified control_details.html,
    # which in turn includes the new assessment_workspace.html partial.
    return templates.TemplateResponse("control_details.html", {"request": request, "control": control})

# --- END OF REVISED main.py ---