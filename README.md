# GRC AI Co-pilot

[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Framework](https://img.shields.io/badge/FastAPI-0.110.0-green.svg)](https://fastapi.tiangolo.com/)
[![Frontend](https://img.shields.io/badge/HTMX-1.9.10-blue)](https://htmx.org/)

This application is an intelligent "Co-pilot" designed to assist Governance, Risk, and Compliance (GRC) professionals. It augments the manual workflow of writing and reviewing control assessments by providing targeted, context-aware AI assistance directly within a streamlined user interface.

The primary goal is to reduce manual effort, improve the quality and consistency of control documentation, and help analysts think more critically about their work, ultimately leading to a stronger compliance posture.

## Functional Specification

This document describes the features and capabilities of the GRC AI Co-pilot.

### 1. Core Application Structure

The application is built around a responsive, dual-pane interface designed for an efficient GRC workflow.

#### 1.1. Master-Detail Layout
-   **Left Sidebar:** A persistent sidebar displays a complete list of all IT controls loaded from the system's data source (`controls.csv`). A dynamic search bar allows for real-time filtering of this list by control name, owner, or risk ID.
-   **Main Content Pane:** This is the primary workspace. Its content dynamically updates based on user actions without requiring a full page reload, powered by HTMX.

#### 1.2. Default View: General GRC Chat
-   **On Initial Load:** The main content pane presents a general-purpose chat interface.
-   **Functionality:** Users can ask non-control-specific questions about GRC best practices, compliance standards, or audit preparation. The AI's responses are grounded by a central knowledge base to ensure they are relevant and helpful.
-   **Interaction:** The interface supports a familiar chat flow where user questions and AI responses are appended to a scrollable history.

#### 1.3. Control-Specific Workspace
-   **Action:** Clicking a control in the sidebar replaces the chat interface with a dedicated workspace for that specific control.
-   **Structured Form:** This workspace provides a structured form with three distinct `textarea` fields for drafting the key components of a control assessment:
    1.  **Control Operation:** How the control works day-to-day.
    2.  **Design & Implementation Details:** The technical specifics of the control.
    3.  **Evidence Description:** The evidence an auditor would need to see.
-   **Session Persistence:** All text entered into these fields is automatically saved to the browser's `localStorage` on a per-control basis, ensuring no work is lost when switching between controls or refreshing the page.

### 2. AI-Powered Assistance Features

The co-pilot's core value comes from its context-aware AI tools, which are available directly within the control-specific workspace.

#### 2.1. Context-Aware "Rephrase"
-   **User Story:** "My draft notes are rough. I want a one-click way to transform them into professional, audit-ready language."
-   **Functionality:** Each `textarea` is accompanied by a **"✍️ Rephrase"** button.
-   **Contextual Grounding:** When clicked, the user's text is sent to the AI along with two layers of context:
    1.  **Control-Specific Context:** The `name` and `description` for the selected control.
    2.  **Best-Practice Context:** Specific guidance loaded from the `guidance/{control_id}.md` file.
-   **Output:** The AI returns a single, professionally rephrased sentence or paragraph, which instantly replaces the user's original text in the `textarea`.

#### 2.2. Context-Aware "Review"
-   **User Story:** "I think my assessment is good, but I want an expert to challenge it and help me find blind spots."
-   **Functionality:** Each `textarea` also has a **"🔍 Review"** button.
-   **Contextual Grounding:** This feature uses the same rich, two-layered context as the "Rephrase" feature.
-   **Persona-Based Output:** The AI is prompted to act as a panel of three senior GRC experts. It returns three potent, insightful questions from the perspective of:
    1.  A **Risk Manager** (focusing on effectiveness).
    2.  A **Compliance Manager** (focusing on policy adherence).
    3.  An **Audit Manager** (focusing on testability and evidence).
-   **UI Response:** The questions appear in a distinct card directly below the relevant section, prompting the user to consider their work more deeply.

### 3. Supporting Systems & UI Feedback

#### 3.1. Dynamic Best-Practice System
-   **Architecture:** The application's knowledge base is designed to be easily extendable. Best practices for each control are stored in individual Markdown files within a `guidance/` directory (e.g., `guidance/AC-02.md`).
-   **Extensibility:** To add guidance for a new control, an administrator simply needs to add a new file to this directory.

#### 3.2. Real-time Status Bar
-   A persistent footer provides users with system feedback after every interaction. It displays:
    1.  **Controls Loaded:** The total number of controls available.
    2.  **Best Practices Considered:** When a control is selected, this dynamically shows how many best practices from its specific guidance file are being used to inform the AI.
    3.  **Server Response Time:** The processing time in milliseconds for the last action, providing transparency on system performance.

#### 3.3. Security and Logging
-   **Access Control:** The entire application is protected by a simple passcode wall, implemented via FastAPI middleware to prevent unauthorized access.
-   **Formatted Logging:** The backend is configured with a custom logger that outputs structured, readable logs to the console in the format: `YYYY-MM-DD HH:MM | endpoint_name | log_message`, aiding in development and debugging.

## Technology Stack

-   **Backend:** FastAPI, Uvicorn, Gunicorn
-   **AI Integration:** Google Vertex AI with the Gemini model
-   **Frontend:** HTMX (for dynamic UI updates), Tailwind CSS (for styling)
-   **Data Source:** CSV file (`controls.csv`) for prototype simplicity
-   **Deployment:** Containerized with Docker and deployed on Google Cloud Run

## Setup and Deployment

### Local Development

1.  **Clone the repository:** `git clone ...`
2.  **Create a virtual environment:** `python -m venv venv && source venv/bin/activate`
3.  **Install dependencies:** `pip install -r requirements.txt` and `npm install`
4.  **Create `.env` file:** Copy `.env.example` to `.env` and fill in your `DEMO_PASSCODE` and `SECRET_KEY`.
5.  **Run the Tailwind build watch:** `npx tailwindcss -i ./src/input.css -o ./static/styles.css --watch`
6.  **Run the FastAPI server:** In a separate terminal, run `uvicorn main:app --reload`

### Cloud Deployment

1.  Authenticate `gcloud`: `gcloud auth login` and set your project.
2.  Ensure you have a `Dockerfile` in your project root.
3.  Generate a `YOUR_SECRET_KEY` with `openssl rand -hex 32`
4.  Deploy using the `gcloud run deploy` command, providing environment variables:
    ```bash
    gcloud run deploy gcr-copilot \
      --source . \
      --region us-central1 \
      --allow-unauthenticated \
      --set-env-vars="SECRET_KEY=YOUR_SECRET_KEY"
    ```

### Load BQ dataset tables

1.  Starter dataset for user management.

```bash
bq load \
  --source_format=CSV \
  --skip_leading_rows=1 \
  --autodetect \
  feedback.users \
  ./users.csv \
  username:STRING,email:STRING,token:STRING,role:STRING,created_on:TIMESTAMP
``` 