from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List
import uuid

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# In-memory data store
class Control(BaseModel):
    id: str
    name: str
    risk_id: str
    status: str
    owner: str

controls: List[Control] = [
    Control(id=str(uuid.uuid4()), name="Access Control", risk_id="R1", status="Active", owner="Alice"),
    Control(id=str(uuid.uuid4()), name="Data Encryption", risk_id="R2", status="Pending", owner="Bob")
]

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "controls": controls})

@app.post("/controls", response_class=HTMLResponse)
async def create_control(request: Request, name: str = Form(...), risk_id: str = Form(...), status: str = Form(...), owner: str = Form(...)):
    control = Control(id=str(uuid.uuid4()), name=name, risk_id=risk_id, status=status, owner=owner)
    controls.append(control)
    return templates.TemplateResponse("control_row.html", {"request": request, "control": control})

@app.get("/controls/{control_id}", response_class=HTMLResponse)
async def get_control(request: Request, control_id: str):
    control = next((c for c in controls if c.id == control_id), None)
    return templates.TemplateResponse("control_details.html", {"request": request, "control": control})

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