# --- START OF FILE main.py ---

import os
from dotenv import load_dotenv
import uuid
import csv
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Request, Form, HTTPException, Response, BackgroundTasks
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

class RefineRequest(BaseModel):
    control_id: str
    current_html: str
    
class QualityCheckRequest(BaseModel):
    assessment_html: str

class TrackEventRequest(BaseModel):
    event_type: str
    control_id: str
    # Add other relevant fields like state_before, state_after etc.

# Define the rubric
QUALITY_RUBRIC = {
    "Specificity": "Is the control description specific and unambiguous? Does it avoid vague terms?",
    "Actionability": "Does the description outline clear, repeatable actions or processes?",
    "Evidence": "Does the description mention or allude to concrete evidence that can be audited (e.g., reports, logs, tickets)?",
    "Clarity": "Is the language clear, concise, and free of jargon? Is it easy for a non-expert to understand?"
}

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


# In main.py


@app.post("/controls/{control_id}/assess", response_class=HTMLResponse)
async def generate_initial_assessment(request: Request, control_id: str):
    """
    Generates the INITIAL baseline assessment for a control by calling the Gemini API,
    using a best-practice document for grounding, and returns the complete
    workspace HTML fragment.
    """
    control = find_control_by_id(control_id)
    if not control:
        raise HTTPException(status_code=404, detail="Control not found")

    # --- ENHANCED PROMPT WITH GROUNDING ---
    # We provide the best_practice.md file as a high-quality example.
    # This "few-shot" prompting guides the model to produce output that
    # matches our desired structure, tone, and level of detail.
    prompt = f"""
    You are an expert IT risk and compliance advisor. Your task is to write a formal control assessment document in Markdown format.
    Use the best-practice framework below as a reference for the structure and quality of your response.

    ---
    **BEST-PRACTICE FRAMEWORK REFERENCE:**
    {BEST_PRACTICE_ASSESSMENT}
    ---

    Now, generate a new assessment for the following specific control:

    **Information Provided:**
    - **Control Name:** "{control.name}"
    - **Risk it Addresses:** "{control.risk_text}"
    - **Current Control Description:** "{control.control_text}"

    **Your Task:**
    Write a concise assessment document that clearly explains why the control is effective at mitigating the specified risk.
    Structure your response with these Markdown sections:
    
    ### Control Assessment: {control.name}

    **1. Summary of Mitigation:**
    A brief paragraph explaining how the control directly addresses the risk.

    **2. Key Mitigation Points:**
    A bulleted list highlighting the specific actions or features of the control that contribute to its effectiveness.

    **3. Potential Evidence for Audit:**
    A bulleted list of potential artifacts an auditor could request to verify the control is operating as described.
    """

    # --- Call Gemini and process the response ---
    if GEMINI_MODEL:
        try:
            # --- LIVE API CALL ---
            print(f"Generating assessment for control ID: {control.id}")
            response = GEMINI_MODEL.generate_content(prompt)
            markdown_text = response.text
            print(f"Successfully received Gemini response for control ID: {control.id}")

        except Exception as e:
            # --- ROBUST ERROR HANDLING ---
            # If the API call fails, log the error and show a user-friendly message.
            print(f"ERROR: Gemini API call failed for control ID {control.id}. Details: {e}")
            markdown_text = """
            ### <span style="color: red;">Error Generating Assessment</span>
            
            An error occurred while communicating with the AI model. Please try again in a few moments.
            If the problem persists, please check the server logs for more details.
            """
    else:
        # Fallback if Gemini is not configured at all
        markdown_text = "### Gemini Not Configured\n\nThis is a placeholder assessment because the AI model is not available."

    html_output = md.render(markdown_text)
    
    # Use dot notation to update the Pydantic model instance
    control.assessment_document = html_output

    # Return the entire workspace partial, now populated with the new assessment
    return templates.TemplateResponse(
        "partials/assessment_workspace.html", # This partial contains the whole flow
        {"request": request, "control": control}
    )

# --- Feature 1.2: Refine Assessment ---
@app.post("/controls/refine", response_class=HTMLResponse)
async def refine_assessment(request: Request, data: RefineRequest):
    """Takes user's current assessment and returns AI-powered refinement snippets."""
    
    # Advanced Prompt for Gemini: Ask for structured JSON output
    prompt = f"""
    You are a GRC expert reviewing the following control assessment.
    Your task is to identify the three weakest areas and provide specific, improved replacement text.

    ASSESSMENT TEXT:
    ---
    {data.current_html}
    ---

    Based on the text, return a JSON array of 3 objects. Each object must have these keys:
    - "rationale": A short (1-2 sentence) reason why this section needs improvement.
    - "original_snippet": The exact, original HTML snippet from the assessment that should be replaced.
    - "revised_snippet": The new, improved HTML snippet.

    Return ONLY the JSON array.
    """
    
    # In a real app, add error handling and JSON parsing
    # response = GEMINI_MODEL.generate_content(prompt)
    # refinements = json.loads(response.text)
    
    # For dev, use mock data
    refinements = [
        {"rationale": "The mention of 'periodic checks' is too vague for an audit.", "original_snippet": "<p>Periodic checks are performed.</p>", "revised_snippet": "<p>A quarterly access review is conducted by the system owner, evidenced by a signed report.</p>"},
        {"rationale": "This lacks a measurable target for remediation.", "original_snippet": "<p>Vulnerabilities are addressed.</p>", "revised_snippet": "<p>Critical vulnerabilities identified are remediated within a 30-day SLA.</p>"},
    ]
    
    return templates.TemplateResponse(
        "partials/refinement_card.html",
        {"request": request, "refinements": refinements}
    )

# --- Feature 1.3: Check Quality ---
@app.post("/controls/check-quality", response_class=HTMLResponse)
async def check_quality(request: Request, data: QualityCheckRequest):
    """Evaluates text against a rubric and returns OOB swap fragments."""
    
    # Prompt for Gemini to evaluate against the rubric
    prompt = f"""
    You are an AI auditor. Evaluate the following assessment text against the quality rubric.
    For each criterion, decide if it is "met" or "unmet".

    RUBRIC:
    {json.dumps(QUALITY_RUBRIC, indent=2)}

    ASSESSMENT TEXT:
    ---
    {data.assessment_html}
    ---

    Return a JSON object with two keys: "met_criteria" and "unmet_criteria",
    which are arrays of the criteria names you evaluated. Example: {{"met_criteria": ["Clarity"], "unmet_criteria": ["Specificity", "Evidence"]}}
    Return ONLY the JSON object.
    """
    
    # In a real app, parse the response from Gemini
    # For dev, use mock data
    results = {"met_criteria": ["Clarity", "Actionability"], "unmet_criteria": ["Specificity", "Evidence"]}

    # Prepare context for the templates
    context = {
        "request": request,
        "results": results,
        "rubric": QUALITY_RUBRIC,
        "total_criteria": len(QUALITY_RUBRIC)
    }
    
    # Render two separate templates for OOB Swap
    status_bar_html = templates.get_template("partials/quality_status_bar.html").render(context)
    modal_html = templates.get_template("partials/quality_modal.html").render(context)
    
    # Combine them into a single response
    return HTMLResponse(content=status_bar_html + modal_html)

#Vertex Evaluation
def log_to_vertex_ai_evaluation(payload: dict):
    """Placeholder for the actual Vertex AI SDK call."""
    print(f"TRACKING EVENT TO VERTEX AI: {payload}")
    # Here you would use the Vertex AI SDK to log this data.
    # e.g., evaluation_service_client.log_event(...)

@app.post("/track_event")
async def track_event(data: TrackEventRequest, background_tasks: BackgroundTasks):
    """Receives tracking events from the frontend and logs them."""
    background_tasks.add_task(log_to_vertex_ai_evaluation, data.dict())
    return {"status": "event received"}