# --- START OF FILE main.py ---

import os
from dotenv import load_dotenv
import uuid
import csv
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Request, Form, HTTPException, Response
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response as StarletteResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# --- Gemini/Vertex AI Integration ---
# We are using the MODERN, UNIFIED SDK for Gemini on Vertex AI.
# This is installed via `pip install google-cloud-aiplatform`.
# As per the migration guide, we use `vertexai.generative_models`.
import vertexai
from vertexai.generative_models import GenerativeModel

# --- Markdown Conversion Library ---
from markdown_it import MarkdownIt 

# --- Configuration ---
# TODO: Replace with your Google Cloud project details
PROJECT_ID = "aicontrol-8c59b"  
LOCATION = "us-central1"
MODEL_NAME = "gemini-2.5-flash" 

# Create an instance of the Markdown parser
md = MarkdownIt()

# Initialize Vertex AI
try:
    # This initialization correctly uses the GCP project context, not an API key.
    # This is the standard for production applications on Google Cloud.
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    
    # Per the migration guide, we instantiate `GenerativeModel` for Gemini models.
    # We are NOT using the deprecated `TextGenerationModel` or `ChatModel`.
    GEMINI_MODEL = GenerativeModel(MODEL_NAME)
    print("Vertex AI and Gemini Model initialized successfully using the modern SDK.")
except Exception as e:
    print(f"Error initializing Vertex AI: {e}")
    print("Gemini features will be disabled.")
    GEMINI_MODEL = None

# Load the best practice document for grounding the model
try:
    BEST_PRACTICE_ASSESSMENT = Path("best_practice.md").read_text()
except FileNotFoundError:
    print("Warning: best_practice.md not found. AI suggestions may be less effective.")
    BEST_PRACTICE_ASSESSMENT = ""

# --- FastAPI App Setup ---
load_dotenv()
app = FastAPI()
DEMO_PASSCODE = os.getenv("DEMO_PASSCODE")
# This key is for signing the cookie. It must be kept secret.
SECRET_KEY = os.getenv("SECRET_KEY") 
COOKIE_NAME = "demo_session"

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- NEW: Middleware for Authentication ---
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # ... The code inside the middleware is correct ...
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
        # Passcode is correct. Set the cookie and tell HTMX to refresh the page.
        response = Response(headers={"HX-Refresh": "true"})
        response.set_cookie(key=COOKIE_NAME, value=passcode, httponly=True, max_age=86400) # 86400s = 1 day
        return response
    else:
        # Passcode is incorrect. Re-render the login form with an error message.
        return templates.TemplateResponse(
            "login_dialog.html",
            {"request": request, "error": "Invalid passcode. Please try again."}
        )


# In-memory data store
# --- Data Model & Loading ---
class Control(BaseModel):
    id: str
    name: str
    risk_id: str
    status: str
    owner: str
    risk_text: str
    control_text: str
    suggestions: Optional[str] = None
    assessment_document: Optional[str] = None

controls: List[Control] = []

def load_controls_from_csv():
    """Loads control data from controls.csv into the in-memory list."""
    try:
        with open("controls.csv", mode='r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            for row in reader:
                controls.append(Control(**row))
        print(f"Loaded {len(controls)} controls from controls.csv")
    except FileNotFoundError:
        print("Error: controls.csv not found. No controls will be loaded.")

load_controls_from_csv()


# --- Helper Function to find a control ---
def find_control_by_id(control_id: str) -> Optional[Control]:
    return next((c for c in controls if c.id == control_id), None)

# --- Standard Endpoints ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "controls": controls})

@app.get("/controls/{control_id}", response_class=HTMLResponse)
async def get_control(request: Request, control_id: str):
    control = find_control_by_id(control_id)
    if not control:
        raise HTTPException(status_code=404, detail="Control not found")
    return templates.TemplateResponse("control_details.html", {"request": request, "control": control})


@app.post("/controls", response_class=HTMLResponse)
async def create_control(request: Request, name: str = Form(...), risk_id: str = Form(...), status: str = Form(...), owner: str = Form(...)):
    control = Control(id=str(uuid.uuid4()), name=name, risk_id=risk_id, status=status, owner=owner)
    controls.append(control)
    return templates.TemplateResponse("control_row.html", {"request": request, "control": control})

@app.post("/controls/{control_id}/update", response_class=HTMLResponse)
async def update_control(request: Request, control_id: str, name: str = Form(...), risk_id: str = Form(...), status: str = Form(...), owner: str = Form(...)):
    for control in controls:
        if control.id == control_id:
            control.name = name
            control.risk_id = risk_id
            control.status = status
            control.owner = owner
            return templates.TemplateResponse("control_details.html", {"request": request, "control": control})
    return HTMLResponse(status_code=404)

# --- Search Endpoint ---

@app.post("/search", response_class=HTMLResponse)
async def search_controls(request: Request, query: str = Form(...)):
    """
    Filters controls based on a search query and returns an HTML fragment
    with the matching control rows.
    """
    search_term = query.lower().strip()
    
    if not search_term:
        # If search is empty, return all controls
        filtered_controls = controls
    else:
        # Filter controls: check name, risk_id, owner, and status
        filtered_controls = [
            c for c in controls if
            search_term in c.name.lower() or
            search_term in c.risk_id.lower() or
            search_term in c.owner.lower() or
            search_term in c.status.lower()
        ]
        
    # Render the partial template with only the filtered controls
    return templates.TemplateResponse(
        "partials/control_list.html", 
        {"request": request, "controls": filtered_controls}
    )

# --- Gemini GenAI Endpoints ---

@app.post("/controls/{control_id}/suggest", response_class=HTMLResponse)
async def suggest_improvements(request: Request, control_id: str):
    if not GEMINI_MODEL:
        return HTMLResponse("<div class='text-red-500 p-2'>Gemini is not configured.</div>")

    control = find_control_by_id(control_id)
    if not control:
        raise HTTPException(status_code=404, detail="Control not found")

    prompt = f"""
    You are a professional IT risk and compliance advisor.
    Your task is to suggest improvements for an existing control based on a best-practice framework.

    **Best-Practice Framework for Reference:**
    ---
    {BEST_PRACTICE_ASSESSMENT}
    ---

    **Existing Control to Analyze:**
    - **Risk it addresses:** "{control.risk_text}"
    - **Current control description:** "{control.control_text}"

    **Your Task:**
    Based on the best-practice framework, provide 3-5 specific, actionable suggestions to make the existing control more robust, measurable, or auditable.
    Present your suggestions as a Markdown bulleted list. Focus on clarity and practicality.
    """

    # Per the migration guide, we call `generate_content()`, not the deprecated `predict()`.
    response = GEMINI_MODEL.generate_content(prompt)
    markdown_text = response.text
    html_output = md.render(markdown_text)
    control.suggestions = html_output
    
    return templates.TemplateResponse("suggestions.html", {"request": request, "control": control})


@app.post("/controls/{control_id}/assess", response_class=HTMLResponse)
async def create_assessment(request: Request, control_id: str):
    if not GEMINI_MODEL:
        return HTMLResponse("<div class='text-red-500 p-2'>Gemini is not configured.</div>")
        
    control = find_control_by_id(control_id)
    if not control:
        raise HTTPException(status_code=404, detail="Control not found")

    prompt = f"""
    You are an expert IT auditor. Your task is to write a formal control assessment document in Markdown format.

    **Information Provided:**
    - **Risk Description:** "{control.risk_text}"
    - **Control Description:** "{control.control_text}"

    **Your Task:**
    Write a concise assessment document that clearly explains why the control is effective at mitigating the specified risk.
    Structure your response with the following sections:
    
    ### Control Assessment: {control.name}

    **1. Summary of Mitigation:**
    A brief paragraph explaining how the control directly addresses the risk.

    **2. Key Mitigation Points:**
    A bulleted list highlighting the specific actions or features of the control that contribute to its effectiveness.

    **3. Potential Evidence for Audit:**
    A bulleted list of potential artifacts an auditor could request to verify the control is operating as described.
    """
    
    # Per the migration guide, we call `generate_content()`.
    response = GEMINI_MODEL.generate_content(prompt)
    markdown_text = response.text
    html_output = md.render(markdown_text)
    control.assessment_document = html_output 

    return templates.TemplateResponse("assessment.html", {"request": request, "control": control})