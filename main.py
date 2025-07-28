# --- START OF REVISED main.py (for v0.1 - Step 1) ---

import os
from dotenv import load_dotenv
import csv
from pathlib import Path
from typing import List, Optional
import time

import vertexai
from vertexai.generative_models import GenerativeModel
from markdown_it import MarkdownIt

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

md = MarkdownIt()

# Configure Gemini API
PROJECT_ID = "aicontrol-8c59b" # Replace with your project ID
LOCATION = "us-central1"
MODEL_NAME = "gemini-2.5-flash" 

try:
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    GEMINI_MODEL = GenerativeModel(MODEL_NAME)
    print("Vertex AI and Gemini Model initialized successfully.")
except Exception as e:
    print(f"Error initializing Vertex AI: {e}. AI features will be disabled.")
    GEMINI_MODEL = None

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
    
class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.start_time = time.time()
        response = await call_next(request)
        return response
    
app.add_middleware(AuthMiddleware)
app.add_middleware(TimingMiddleware)


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

# Load the central guidance document for grounding all prompts
try:
    CENTRAL_GUIDANCE = Path("central_guidance.md").read_text()
    print("Loaded central_guidance.md successfully.")
except FileNotFoundError:
    print("Warning: central_guidance.md not found. AI responses will lack global context.")
    CENTRAL_GUIDANCE = "" # Default to empty string if not found

# --- Helper Function to find a control ---
def find_control_by_id(control_id: str) -> Optional[Control]:
    return next((c for c in controls if c.id == control_id), None)

# --- Core Endpoints ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serves the main index page with the list of all controls."""
    response_time = time.time() - request.state.start_time
    context = {
        "request": request, 
        "controls": controls,
        "controls_count": len(controls),
        "response_time": response_time
    }
    return templates.TemplateResponse("index.html", context)

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
    
    response_time = time.time() - request.state.start_time
    context = {
        "request": request, 
        "control": control,
        "controls_count": len(controls),
        "response_time": response_time
    }

    # This endpoint now renders the simplified control_details.html,
    # which in turn includes the new assessment_workspace.html partial.
    return templates.TemplateResponse("control_details.html", context)

@app.post("/ai/rephrase-text")
async def rephrase_text(
    request: Request,
    text: str = Form(...),
    control_id: str = Form(...),
    element_id: str = Form(...),
    element_name: str = Form(...),
    placeholder: str = Form(...)
):
    """Rephrases text with full context awareness."""
    control = find_control_by_id(control_id)
    if not control:
        return HTMLResponse("Error: Control not found.", status_code=404)
    
    """Takes user text and returns a complete, new textarea element with the rephrased text."""
    if not GEMINI_MODEL:
        rephrased_text = "AI model is not configured."
    elif not text.strip():
        rephrased_text = ""
    else:
        # NEW, MORE RESTRICTIVE PROMPT
        prompt = f"""
        You are a GRC writing assistant. Your task is to rewrite the user's input text to make it sound more professional and concise.

    **GLOBAL BEST PRACTICES FOR REFERENCE:**
    ---
    {CENTRAL_GUIDANCE}
    ---

    **CONTEXT OF THE SPECIFIC CONTROL YOU ARE WORKING ON:**
    - Risk Description: "{control.risk_text}"
    - Overall Control Description: "{control.control_text}"

    **USER'S TEXT TO REPHRASE:**
    ---
    {text}
    ---

    **YOUR TASK:**
    Rewrite the "USER'S TEXT TO REPHRASE" using the provided context. 
        
    **Instructions:**
    1.  Return ONLY the rephrased text.
    2.  Do NOT provide options, explanations, or any surrounding text.
    3.  Do NOT use Markdown formatting.
    4.  Your entire response must be the improved text and nothing else.
    """

        try:
            response = GEMINI_MODEL.generate_content(prompt)
            rephrased_text = response.text.strip()
        except Exception as e:
            rephrased_text = f"Error: Could not rephrase text. Details: {e}"

    response_time = time.time() - request.state.start_time

    context = {
        "request": request,
        "rephrased_text": rephrased_text,
        "element_id": element_id,
        "element_name": element_name,
        "placeholder": placeholder,
        "controls_count": len(controls),
        "response_time": response_time,
    }

    textarea_html = templates.get_template("partials/rephrased_textarea.html").render(context)
    status_bar_html = templates.get_template("partials/status_bar.html").render(context)
    # Combine the snippets into a single response payload
    full_response = textarea_html + status_bar_html
    
    return HTMLResponse(content=full_response)# Return the new textarea element by rendering the partial
    # return templates.TemplateResponse("partials/rephrased_textarea.html", context)

@app.post("/ai/review-text", response_class=HTMLResponse)
async def review_text(request: Request, text: str = Form(...), control_id: str = Form(...)):
    """Takes user text and returns critical questions from three GRC personas."""
    if not GEMINI_MODEL:
        return HTMLResponse("<p class='text-red-500'>AI model not configured.</p>")
    
    control = find_control_by_id(control_id)
    if not control:
        return HTMLResponse("Error: Control not found.", status_code=404)
    
    # CONTEXT-AWARE PROMPT
    prompt = f"""
    You are a panel of three senior GRC experts reviewing a specific piece of a control assessment.

    **GLOBAL BEST PRACTICES FOR REFERENCE:**
    ---
    {CENTRAL_GUIDANCE}
    ---

    **CONTEXT OF THE SPECIFIC CONTROL YOU ARE WORKING ON:**
    - Risk Description: "{control.risk_text}"
    - Overall Control Description: "{control.control_text}"

    **SPECIFIC TEXT SNIPPET TO REVIEW:**
    ---
    {text}
    ---

    YOUR TASK:
    Based on all the provided context, ask one potent, insightful question from each of your expert perspectives that challenges the "SPECIFIC TEXT SNIPPET TO REVIEW". Present your response as a Markdown formatted list.

    - **As a Risk Manager:** [Your question, focusing on risk mitigation effectiveness and impact]
    - **As a Compliance Manager:** [Your question, focusing on adherence to policy, standards, or regulations]
    - **As an Audit Manager:** [Your question, focusing on testability, evidence, and repeatability]
    """
    try:
        response = GEMINI_MODEL.generate_content(prompt)
        # Convert the Markdown list from Gemini into HTML
        questions_html = md.render(response.text)
        
       # 1. Calculate the response time
        response_time = time.time() - request.state.start_time

        # 2. Prepare a context dictionary for ALL templates
        context = {
            "request": request,
            "questions_html": questions_html,
            "controls_count": len(controls),
            "response_time": response_time,
        }

        # 3. Render both HTML snippets
        review_card_html = templates.get_template("partials/review_questions.html").render(context)
        status_bar_html = templates.get_template("partials/status_bar.html").render(context)

        # 4. Combine the snippets into a single response payload
        full_response = review_card_html + status_bar_html
        
        return HTMLResponse(content=full_response)
    
    except Exception as e:
        return HTMLResponse(content=f"<p class='text-red-500'>Error during AI processing: {e}</p>")
