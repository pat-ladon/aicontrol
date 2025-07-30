# --- START OF REVISED main.py (for v0.1 - Step 1) ---

import os
import json
from dotenv import load_dotenv
import csv
from pathlib import Path
from typing import List, Optional, Dict
import time
import logging
import secrets
from datetime import datetime
import uuid

import vertexai
from vertexai.generative_models import GenerativeModel
from markdown_it import MarkdownIt

from fastapi import FastAPI, Request, Form, HTTPException, Response
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# --- logging configuration ---
# Create a custom formatter
log_formatter = logging.Formatter(
    "%(asctime)s | %(funcName)s | %(message)s", datefmt="%Y-%m-%d %H:%M"
)

# Get the root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Remove any existing handlers to avoid duplicates
root_logger.handlers.clear()

# Create a new handler to print to console and apply the formatter
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
root_logger.addHandler(console_handler)
# --- logging configuration ---

# --- FastAPI App Setup ---
load_dotenv()
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
SECRET_KEY = os.getenv("SECRET_KEY")
COOKIE_NAME = "auth_token_session"

md = MarkdownIt()

# Configure Gemini API
PROJECT_ID = "aicontrol-8c59b"  # Replace with your project ID
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


# --- Pydantic model for a user ---


# --- Data Model & Loading ---
class User(BaseModel):
    username: str
    token: str
    role: str
    created_on: str


class Section(BaseModel):
    id_slug: str
    title: str
    helper_text: str
    placeholder: str


class Control(BaseModel):
    id: str
    name: str
    risk_id: Optional[str] = None
    status: Optional[str] = None
    owner: Optional[str] = None
    risk_text: Optional[str] = None
    description: str
    sections: List[Section]
    # Removed AI-related fields like 'suggestions' and 'assessment_document' for now


users_by_token: Dict[str, User] = {}
controls: List[Control] = []

# --- Dictionary to hold users for fast lookups ---
users_by_token: Dict[str, User] = {}


def load_users_from_csv():
    """Loads users from users.csv into a dictionary keyed by token."""
    try:
        with open("users.csv", mode="r", encoding="utf-8") as infile:
            reader = csv.DictReader(infile)
            for row in reader:
                user = User(**row)
                users_by_token[user.token] = user
        print(f"Loaded {len(users_by_token)} users from users.csv")
    except FileNotFoundError:
        print("Error: users.csv not found. No users will be loaded.")


def load_controls_from_csv():
    """Loads and parses control data, including the dynamic sections."""
    try:
        with open("controls.csv", mode="r", encoding="utf-8") as infile:
            reader = csv.DictReader(infile)
            for row in reader:
                # Parse the JSON string from the 'sections' column
                if "sections" in row and row["sections"]:
                    row["sections"] = json.loads(row["sections"])
                else:
                    row["sections"] = (
                        []
                    )  # Default to an empty list if column is missing/empty
                controls.append(Control(**row))
        print(f"Loaded {len(controls)} controls from controls.csv")
    except FileNotFoundError:
        print("Error: controls.csv not found. No controls will be loaded.")


# Load data on startup
load_controls_from_csv()
load_users_from_csv()


# --- Middleware for Authentication ---
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in [
            "/login",
            "/favicon.ico",
        ] or request.url.path.startswith("/static"):
            return await call_next(request)
        token_in_cookie = request.cookies.get(COOKIE_NAME)
        if token_in_cookie and token_in_cookie in users_by_token:
            # This is the key change: we attach the *entire* user object.
            request.state.user = users_by_token[token_in_cookie]
            return await call_next(request)
        return templates.TemplateResponse(
            "login_dialog.html", {"request": request, "error": None}
        )


class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.start_time = time.time()
        response = await call_next(request)
        return response


app.add_middleware(AuthMiddleware)
app.add_middleware(TimingMiddleware)


def load_best_practices(control_id: str) -> tuple[str, int]:
    """Loads best practice content and counts the items for a specific control."""
    try:
        guidance_path = Path(f"guidance/{control_id}.md")
        content = guidance_path.read_text()
        # Count lines starting with '*' or '-' as a simple heuristic for number of practices
        practice_count = sum(
            1 for line in content.splitlines() if line.strip().startswith(("*", "-"))
        )
        return content, practice_count
    except FileNotFoundError:
        # If no specific guidance exists, return empty values gracefully
        return "", 0


# --- Helper Function to find a control ---
def find_control_by_id(control_id: str) -> Optional[Control]:
    return next((c for c in controls if c.id == control_id), None)


# --- Login Endpoint ---
@app.post("/login")
async def login(request: Request, token: str = Form(...)):
    if token in users_by_token:
        response = Response(headers={"HX-Refresh": "true"})
        response.set_cookie(key=COOKIE_NAME, value=token, httponly=True, max_age=86400)
        return response
    else:
        return templates.TemplateResponse(
            "login_dialog.html",
            {"request": request, "error": "Invalid token. Please try again."},
        )


# --- Core Endpoints ---


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serves the main index page with the list of all controls."""
    response_time = time.time() - request.state.start_time
    user = getattr(request.state, "user", None)
    context = {
        "request": request,
        "controls": controls,
        "controls_count": len(controls),
        "response_time": response_time,
        "user": user,
    }
    return templates.TemplateResponse("index.html", context)


@app.get("/chat", response_class=HTMLResponse)
async def get_chat_workspace(request: Request):
    """Returns the HTML fragment for the general chat workspace."""
    # We don't need to pass much context here, just the request object
    return templates.TemplateResponse(
        "partials/chat_workspace.html", {"request": request}
    )


@app.post("/search", response_class=HTMLResponse)
async def search_controls(request: Request, query: str = Form(...)):
    """Filters controls and returns the updated list as an HTML fragment."""
    search_term = query.lower().strip()
    if not search_term:
        filtered_controls = controls
    else:
        filtered_controls = [
            c
            for c in controls
            if search_term in c.name.lower()
            or search_term in c.risk_id.lower()
            or search_term in c.owner.lower()
            or search_term in c.status.lower()
        ]
    return templates.TemplateResponse(
        "partials/control_list.html",
        {"request": request, "controls": filtered_controls},
    )


@app.get("/controls/{control_id}", response_class=HTMLResponse)
async def get_control(request: Request, control_id: str):
    """
    Serves the control detail view. This is the endpoint that renders our new
    structured assessment form.
    """
    control = find_control_by_id(control_id)
    user = getattr(request.state, "user", None)
    if not control:
        raise HTTPException(status_code=404, detail="Control not found")

    _, best_practices_count = load_best_practices(control.id)

    response_time = time.time() - request.state.start_time
    context = {
        "request": request,
        "control": control,
        "controls_count": len(controls),
        "response_time": response_time,
        "best_practices_count": best_practices_count,
        "username": user.username if user else None,
    }

    # This endpoint now renders the simplified control_details.html,
    # which in turn includes the new assessment_workspace.html partial.
    return templates.TemplateResponse("control_details.html", context)


@app.post("/ai/rephrase-text")
async def rephrase_text(
    request: Request,
    text: str = Form(...),
    control_id: str = Form(...),
    section_title: str = Form(...),
    element_id: str = Form(...),
    element_name: str = Form(...),
    placeholder: str = Form(...),
):
    """Rephrases text with full context awareness."""
    control = find_control_by_id(control_id)
    if not control:
        return HTMLResponse("Error: Control not found.", status_code=404)

    logging.info(
        f"Rephrasing text for control '{control_id}' in section '{element_name}'"
    )
    best_practices, best_practices_count = load_best_practices(control_id)

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
    {best_practices}
    ---

    **CONTEXT OF THE SPECIFIC CONTROL YOU ARE WORKING ON:**
    - Risk Description: "{control.name}"
    - Overall Control Description: "{control.description}"

    You are rephrasing the text for the following specific section of the assessment:
    - SECTION TITLE: "{section_title}"

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
        "best_practices_count": best_practices_count,
    }

    textarea_html = templates.get_template("partials/rephrased_textarea.html").render(
        context
    )
    status_bar_html = templates.get_template("partials/status_bar.html").render(context)
    # Combine the snippets into a single response payload
    full_response = textarea_html + status_bar_html

    return HTMLResponse(
        content=full_response
    )  # Return the new textarea element by rendering the partial
    # return templates.TemplateResponse("partials/rephrased_textarea.html", context)


@app.post("/ai/review-text", response_class=HTMLResponse)
async def review_text(
    request: Request, text: str = Form(...), control_id: str = Form(...)
):
    """Takes user text and returns critical questions from three GRC personas."""
    if not GEMINI_MODEL:
        return HTMLResponse("<p class='text-red-500'>AI model not configured.</p>")

    best_practices, best_practices_count = load_best_practices(control_id)

    control = find_control_by_id(control_id)
    if not control:
        return HTMLResponse("Error: Control not found.", status_code=404)

    # CONTEXT-AWARE PROMPT
    prompt = f"""
    You are a panel of three senior GRC experts reviewing a specific piece of a control assessment.

    **GLOBAL BEST PRACTICES FOR REFERENCE:**
    ---
    {best_practices}
    ---

    **CONTEXT OF THE SPECIFIC CONTROL YOU ARE WORKING ON:**
    - Risk Description: "{control.risk_text}"
    - Overall Control Description: "{control.description}"

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
            "best_practices_count": best_practices_count,
        }

        # 3. Render both HTML snippets
        review_card_html = templates.get_template(
            "partials/review_questions.html"
        ).render(context)
        status_bar_html = templates.get_template("partials/status_bar.html").render(
            context
        )

        # 4. Combine the snippets into a single response payload
        full_response = review_card_html + status_bar_html

        return HTMLResponse(content=full_response)

    except Exception as e:
        return HTMLResponse(
            content=f"<p class='text-red-500'>Error during AI processing: {e}</p>"
        )


@app.post("/ai/chat", response_class=HTMLResponse)
async def general_chat(request: Request, user_message: str = Form(...)):
    """Handles general, non-control-specific chat requests."""
    if not GEMINI_MODEL:
        return HTMLResponse("<p class='text-red-500'>AI model not configured.</p>")

    # Use the central guidance to keep the chat focused on GRC topics
    prompt = f"""
    You are a helpful and professional GRC (Governance, Risk, and Compliance) assistant.
    Use the following best practices to inform your answers.

    **BEST PRACTICES REFERENCE:**
    ---
    Assume GRC standards provide best practices.
    ---

    **USER'S QUESTION:**
    {user_message}
    """

    try:
        response = GEMINI_MODEL.generate_content(prompt)
        ai_response_html = md.render(response.text)

        # --- OOB Swap Logic ---
        response_time = time.time() - request.state.start_time
        context = {
            "request": request,
            "user_message": user_message,
            "ai_response_html": ai_response_html,
            "controls_count": len(controls),
            "response_time": response_time,
        }

        chat_pair_html = templates.get_template(
            "partials/chat_message_pair.html"
        ).render(context)
        status_bar_html = templates.get_template("partials/status_bar.html").render(
            context
        )

        return HTMLResponse(content=chat_pair_html + status_bar_html)

    except Exception as e:
        return HTMLResponse(
            content=f"<p class='text-red-500'>Error during AI processing: {e}</p>"
        )


# --- Admin Endpoints ---


@app.get("/admin/users", response_class=HTMLResponse)
async def manage_users_page(request: Request):
    """Serves the user management page as a workspace fragment with status bar update."""
    user = getattr(request.state, "user", None)
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Access Forbidden")

    all_users = list(users_by_token.values())
    response_time = time.time() - request.state.start_time

    context = {
        "request": request,
        "user": user,
        "all_users": all_users,
        "controls_count": len(controls),
        "response_time": response_time,
        # We don't have a specific control, so no 'best_practices_count'
    }

    # Render both the main content and the status bar for a full workspace update
    users_page_html = templates.get_template("admin/users.html").render(context)
    status_bar_html = templates.get_template("partials/status_bar.html").render(context)

    return HTMLResponse(content=users_page_html + status_bar_html)


# In app/main.py


@app.post("/admin/users/add", response_class=HTMLResponse)
async def add_user(request: Request, username: str = Form(...), role: str = Form(...)):
    """Handles the creation of a new user."""
    user = getattr(request.state, "user", None)
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Access Forbidden")

    new_token = secrets.token_hex(16)
    created_on = datetime.utcnow().isoformat() + "Z"
    new_user = User(
        username=username, token=new_token, role=role, created_on=created_on
    )

    script_dir = Path(__file__).parent  # This gets the project root directory
    csv_path = script_dir / "users.csv"

    try:
        # Use the explicit path variable here
        with open(csv_path, mode="a", newline="", encoding="utf-8") as outfile:
            writer = csv.writer(outfile)
            writer.writerow(
                [new_user.username, new_user.token, new_user.role, new_user.created_on]
            )
    except Exception as e:
        logging.error(f"Failed to write new user to {csv_path}: {e}")
        raise HTTPException(status_code=500, detail="Could not save new user.")

    users_by_token[new_user.token] = new_user
    logging.info(f"Admin '{user.username}' created new user '{new_user.username}'")

    return templates.TemplateResponse(
        "partials/user_row.html", {"request": request, "user_to_display": new_user}
    )


@app.get("/admin/users/token/{token_value}", response_class=HTMLResponse)
async def show_full_token(request: Request, token_value: str):
    """Returns an HTML fragment displaying the full token and a 'Hide' button."""
    user = getattr(request.state, "user", None)
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return templates.TemplateResponse(
        "partials/token_revealed.html", {"request": request, "token": token_value}
    )


@app.get("/admin/users/token/hide/{token_value}", response_class=HTMLResponse)
async def hide_full_token(request: Request, token_value: str):
    """Returns the original 'Show Token' button fragment."""
    user = getattr(request.state, "user", None)
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return templates.TemplateResponse(
        "partials/token_hidden.html", {"request": request, "token": token_value}
    )


@app.delete("/admin/users/delete/{token}", status_code=200)
async def delete_user(request: Request, token: str):
    """Handles the deletion of a user."""
    user = getattr(request.state, "user", None)
    # --- SECURITY: Ensure only admins can perform this action ---
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    # Find the user to be deleted for logging purposes
    user_to_delete = users_by_token.get(token)
    if not user_to_delete:
        raise HTTPException(status_code=404, detail="User not found")

    # --- 1. Remove from in-memory dictionary ---
    del users_by_token[token]
    logging.info(
        f"Admin '{user.username}' deleted user '{user_to_delete.username}' (token: {token})"
    )

    # --- 2. Rewrite the CSV file without the deleted user ---
    # This is the safest way to remove a row from a CSV
    script_dir = Path(__file__).parent
    csv_path = script_dir / "users.csv"

    # Read all current users into a list
    current_users = []
    with open(csv_path, mode="r", newline="", encoding="utf-8") as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            # Add every user EXCEPT the one we are deleting
            if row["token"] != token:
                current_users.append(row)

    # Write the filtered list back to the file, overwriting it
    with open(csv_path, mode="w", newline="", encoding="utf-8") as outfile:
        # Use the same fieldnames as the original file
        writer = csv.DictWriter(
            outfile, fieldnames=["username", "token", "role", "created_on"]
        )
        writer.writeheader()
        writer.writerows(current_users)

    # 3. Return an empty 200 OK response. HTMX will use this to remove the row.
    return Response(status_code=200)


# --- NEW: Placeholder for Manage Controls ---
@app.get("/admin/controls", response_class=HTMLResponse)
async def manage_controls_page(request: Request):
    """Serves the control management page as a workspace fragment."""
    user = getattr(request.state, "user", None)
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    response_time = time.time() - request.state.start_time
    context = {
        "request": request,
        "user": user,
        "all_controls": controls,  # Pass the full list of controls
        "controls_count": len(controls),
        "response_time": response_time,
    }

    controls_page_html = templates.get_template("admin/controls.html").render(context)
    status_bar_html = templates.get_template("partials/status_bar.html").render(context)

    return HTMLResponse(content=controls_page_html + status_bar_html)


@app.post("/admin/controls/add", response_class=HTMLResponse)
async def add_control(
    request: Request,
    name: str = Form(...),
    risk_id: str = Form(...),
    owner: str = Form(...),
    risk_text: str = Form(...),
    description: str = Form(...),
):
    """Handles the creation of a new control."""
    user = getattr(request.state, "user", None)
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    # 1. Generate new control data
    new_id = str(uuid.uuid4())  # Generate a unique ID for the new control
    new_control = Control(
        id=new_id,
        name=name,
        risk_id=risk_id,
        status="Active",
        owner=owner,
        risk_text=risk_text,
        description=description,
        sections=[],  # New controls start with empty sections
    )

    # 2. Append to the CSV file
    csv_path = Path(__file__).parent / "controls.csv"
    try:
        with open(csv_path, mode="a", newline="", encoding="utf-8") as outfile:
            writer = csv.writer(outfile)
            # Match the order of your CSV headers
            writer.writerow(
                [
                    new_control.id,
                    new_control.name,
                    new_control.risk_id,
                    new_control.status,
                    new_control.owner,
                    new_control.risk_text,
                    new_control.description,
                    "[]",
                ]
            )
    except Exception as e:
        logging.error(f"Failed to write new control to controls.csv: {e}")
        raise HTTPException(status_code=500, detail="Could not save new control.")

    # 3. Add to the in-memory list
    controls.append(new_control)
    logging.info(f"Admin '{user.username}' created new control '{new_control.name}'")

    # 4. Return an HTML fragment of the new control row for HTMX
    return templates.TemplateResponse(
        "partials/control_admin_row.html",
        {"request": request, "control_to_display": new_control},
    )


@app.delete("/admin/controls/delete/{control_id}", status_code=200)
async def delete_control(request: Request, control_id: str):
    """Handles the deletion of a control."""
    user = getattr(request.state, "user", None)
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    control_to_delete = find_control_by_id(control_id)
    if not control_to_delete:
        raise HTTPException(status_code=404, detail="Control not found")

    # 1. Remove from in-memory list
    controls.remove(control_to_delete)
    logging.info(
        f"Admin '{user.username}' deleted control '{control_to_delete.name}' (ID: {control_id})"
    )

    # 2. Rewrite the CSV file without the deleted control
    csv_path = Path(__file__).parent / "controls.csv"
    current_controls_dict = [c.model_dump() for c in controls]

    with open(csv_path, mode="w", newline="", encoding="utf-8") as outfile:
        # Important: Get the fieldnames from the Pydantic model to ensure order
        writer = csv.DictWriter(outfile, fieldnames=Control.model_fields.keys())
        writer.writeheader()
        for control_dict in current_controls_dict:
            # Convert the 'sections' list back to a JSON string for CSV storage
            control_dict["sections"] = json.dumps(control_dict["sections"])
            writer.writerow(control_dict)

    # 3. Return an empty 200 OK response for HTMX
    return Response(status_code=200)


@app.get("/admin/controls/edit/{control_id}", response_class=HTMLResponse)
async def get_control_edit_form(request: Request, control_id: str):
    """Returns an HTML fragment of the edit form for a specific control."""
    user = getattr(request.state, "user", None)
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    control_to_edit = find_control_by_id(control_id)
    if not control_to_edit:
        raise HTTPException(status_code=404, detail="Control not found")

    return templates.TemplateResponse(
        "partials/control_admin_edit_form.html",
        {"request": request, "control_to_edit": control_to_edit},
    )


@app.get("/admin/controls/row/{control_id}", response_class=HTMLResponse)
async def get_control_row(request: Request, control_id: str):
    """Returns an HTML fragment of a single read-only control row."""
    user = getattr(request.state, "user", None)
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    control_to_display = find_control_by_id(control_id)
    if not control_to_display:
        return HTMLResponse("<tr><td colspan='3'>Error: Control not found.</td></tr>")

    return templates.TemplateResponse(
        "partials/control_admin_row.html",
        {"request": request, "control_to_display": control_to_display},
    )


@app.put("/admin/controls/update/{control_id}", response_class=HTMLResponse)
async def update_control(request: Request, control_id: str):
    """Handles the update of an existing control's data."""
    user = getattr(request.state, "user", None)
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    control_to_update = find_control_by_id(control_id)
    if not control_to_update:
        raise HTTPException(status_code=404, detail="Control not found")

    form_data = await request.form()

    # Update main attributes
    control_to_update.name = form_data.get("name")
    control_to_update.risk_id = form_data.get("risk_id")
    control_to_update.owner = form_data.get("owner")
    control_to_update.risk_text = form_data.get("risk_text")
    control_to_update.description = form_data.get("description")

    # Reconstruct the sections list from the indexed form data
    new_sections = []
    i = 0
    while True:
        if f"section_id_slug_{i}" in form_data:
            new_sections.append(
                Section(
                    id_slug=form_data.get(f"section_id_slug_{i}"),
                    title=form_data.get(f"section_title_{i}"),
                    helper_text=form_data.get(f"section_helper_text_{i}"),
                    placeholder=form_data.get(f"section_placeholder_{i}"),
                )
            )
            i += 1
        else:
            break
    control_to_update.sections = new_sections

    # --- Rewrite the entire CSV file to persist the changes ---
    csv_path = Path(__file__).parent / "controls.csv"
    current_controls_dict = [c.model_dump() for c in controls]

    with open(csv_path, mode="w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=Control.model_fields.keys())
        writer.writeheader()
        for control_dict in current_controls_dict:
            control_dict["sections"] = json.dumps(control_dict["sections"])
            writer.writerow(control_dict)

    logging.info(f"Admin '{user.username}' updated control '{control_to_update.name}'")

    # Return the updated read-only row to swap back into the table
    return templates.TemplateResponse(
        "partials/control_admin_row.html",
        {"request": request, "control_to_display": control_to_update},
    )


@app.get("/admin/controls/sections/new", response_class=HTMLResponse)
async def get_new_section_row(request: Request, index: int):
    """Returns an HTML fragment for a new, blank workspace section row."""
    user = getattr(request.state, "user", None)
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    # We pass the 'index' to ensure the form field names are unique
    return templates.TemplateResponse(
        "partials/control_admin_edit_section_row.html",
        {"request": request, "section": None, "loop": {"index0": index}},
    )
