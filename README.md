# AI-Powered GRC Control Co-pilot

[![Release](https://img.shields.io/github/v/release/pat-ladon/aicontrol)](https://github.com/pat-ladon/aicontrol/releases)
[![Python Version](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![Framework](https://img.shields.io/badge/FastAPI-0.110.0-green.svg)](https://fastapi.tiangolo.com/)
[![Deployed On](https://img.shields.io/badge/Deployed%20On-Google%20Cloud%20Run-lightgrey.svg)](https://cloud.google.com/run)

This application is a prototype of an AI-powered "Co-pilot" designed to assist GRC analysts, IT auditors, and control owners in their daily tasks. It leverages a generative AI backend (Google Gemini) to accelerate the creation of high-quality control documentation and proactively identify areas for control improvement.

The primary goal is to reduce the manual effort, enhance the consistency, and improve the quality of control assessments, ultimately leading to a stronger compliance posture and more efficient audit cycles.

**Live Demo:** `https://aicontrol-xxxxxxxx-uc.a.run.app` (Protected by demo passcode)

## Functional Specification

### 1. Core GRC Workflow

The application provides a foundational interface for managing a catalog of IT general controls.

#### 1.1. Control Listing & Master-Detail View

- **Description:** On launch, the system presents a master-detail layout. A scrollable list of all controls is displayed in the left-hand navigation pane.
- **UI:** The list view is compact, displaying the control `Name`, `Owner`, and `Risk ID` for quick identification.
- **Action:** Clicking a control in the list dynamically loads its full details into the main content area without a page refresh.

#### 1.2. Control Detail View

- **Description:** The main content area displays the full, read-only details for the selected control, including its name, status, owner, a detailed `Risk Description`, and the current `Control Description`.
- **Acceptance Criteria:** All data loaded from the master `controls.csv` is accurately displayed.

#### 1.3. Dynamic Search & Filtering

- **Description:** A search bar in the left pane allows for real-time, dynamic filtering of the control list.
- **Logic:** The search is performed against the control's name, owner, risk ID, and status. The list updates instantly as the user types.
- **Technology:** Implemented via HTMX, this functionality sends search queries to the backend and swaps the table body with the filtered results, preventing full page reloads.

### 2. AI-Powered Enrichment (Core Features)

This is the primary value-add of the application, where generative AI assists the user in analyzing and documenting controls.

#### 2.1. AI-Generated Control Assessment

- **User Story:** As a GRC analyst, I want to automatically generate a formal assessment document for a control, so that I can ensure a standardized, auditable rationale is recorded for how it mitigates its associated risk.
- **Action:** From the control detail view, the user clicks the "Generate Assessment" button.
- **System Process:**
  1.  The backend sends the specific `Risk Description` and `Control Description` to the Google Gemini API.
  2.  The prompt instructs the model to act as an expert IT auditor and generate a structured document in Markdown format.
  3.  The generated document includes a "Summary of Mitigation," "Key Mitigation Points," and "Potential Evidence for Audit."
- **UI Response:** The backend converts the generated Markdown to HTML and sends the formatted snippet back to the client. HTMX swaps this content into a designated area below the control details, rendering it instantly.

#### 2.2. AI-Powered Improvement Suggestions

- **User Story:** As a control owner, I want to receive actionable suggestions on how to improve my control, so that I can proactively strengthen our security posture and mature our control environment.
- **Action:** From the control detail view, the user clicks the "Suggest Improvements" button.
- **System Process:**
  1.  The backend sends the control's risk/description text to the Gemini API.
  2.  **Crucially, the prompt is "grounded"** with the content of `best_practice.md`, which contains a framework for a best-in-class control.
  3.  The model is instructed to compare the user's current control against the best-practice framework and provide 3-5 specific, actionable recommendations for improvement (e.g., adding metrics, improving automation, enhancing evidence collection).
- **UI Response:** The generated list of suggestions is converted from Markdown to HTML and rendered dynamically in the UI via HTMX.

### 3. Security

#### 3.1. Demo Access Control

- **Description:** To protect the application and prevent unauthorized use of the Gemini API during a demo, the entire application is protected by a "passcode wall."
- **Implementation:** A FastAPI middleware intercepts all incoming requests. If a valid session cookie is not present, the user is presented with a full-screen HTML dialog prompting for a passcode.
- **Acceptance Criteria:** No application endpoints (except `/login`) are accessible without first submitting the correct passcode.

## Technology Stack & Architecture

- **Backend:**
  - **Framework:** FastAPI
  - **Web Server:** Gunicorn with Uvicorn workers (for production)
  - **AI:** Google Gemini via the `google-cloud-aiplatform` SDK
  - **Data Source:** CSV file (for prototype simplicity)
- **Frontend:**
  - **Dynamic UI:** HTMX
  - **Styling:** Tailwind CSS (with Typography plugin)
- **Deployment Architecture:**
  - **Platform:** Google Cloud Run
  - **Method:** The application is packaged as a container using a `Dockerfile`. The `gcloud run deploy` command builds this container, pushes it to Google Artifact Registry, and deploys it as a serverless, auto-scaling service. This architecture is cost-effective (scales to zero) and highly scalable.

## Setup and Deployment

### Prerequisites

- Python 3.11+
- Google Cloud SDK (`gcloud`) authenticated to your account
- Node.js and npm (for managing Tailwind CSS)

### Local Development

1.  **Clone the repository:** `git clone https://github.com/YOUR_USER/aicontrol.git`
2.  **Create a virtual environment:** `python -m venv venv && source venv/bin/activate`
3.  **Install dependencies:** `pip install -r requirements.txt` and `npm install`
4.  **Create `.env` file:** Copy `.env.example` to `.env` and fill in your `DEMO_PASSCODE` and `SECRET_KEY`.
5.  **Run the Tailwind build:** `npx tailwindcss -i ./src/input.css -o ./static/styles.css --watch`
6.  **Run the FastAPI server:** `uvicorn main:app --reload`

### Cloud Deployment

1.  **Authenticate gcloud:** `gcloud auth login`
2.  **Set your project:** `gcloud config set project YOUR_GCP_PROJECT_ID`
3.  **Enable APIs:** `gcloud services enable run.googleapis.com artifactregistry.googleapis.com`
4.  **Deploy:** Run the `gcloud run deploy` command, passing secrets via `--set-env-vars`:
    ```bash
    gcloud run deploy aicontrol \
      --source . \
      --region us-central1 \
      --allow-unauthenticated \
      --set-env-vars="DEMO_PASSCODE=YOUR_DEMO_PASSCODE,SECRET_KEY=YOUR_SECRET_KEY"
    ```
