# Functional Specification: Open GRC v0.0.2 - Interactive Assessment Workspace

**Version:** 0.0.2
**Date:** July 6, 2025
**Author:** Patrick

## 1. Product Vision & Goals

Version 2.1 of the AI-Powered GRC Control Co-pilot refines the application into an intelligent and interactive **assessment workspace**.

The primary goal is to empower GRC analysts and control owners to **iteratively craft, refine, and improve** their control assessments directly within the application. This will be achieved by introducing stateful, per-control workspaces with session persistence, contextual AI-driven refinement suggestions, and a qualitative feedback system designed to guide, not grade.

We are explicitly **removing a numerical score** to reduce user anxiety and focus them on actionable improvements, ensuring a more intuitive and encouraging user experience. A supporting backend tracking system will measure the effectiveness of our AI assistance for continuous product improvement.

## 2. Core Data Model: Per-Control Session State

To enable iterative, per-control work, all session-specific data will be stored in the user's browser `localStorage`. This data is structured to be isolated for each control and easily extendible.

- **Storage Mechanism:** Browser `localStorage`
- **Key Naming Convention:** `grc-copilot-assessment-{control_id}`
  - _Example:_ `grc-copilot-assessment-AC-02`
- **Value Data Structure:** A JSON object with the following schema:

```json
{
  "controlId": "string", // e.g., "AC-02"
  "lastModified": "ISO_8601_timestamp", // Updated on every change
  "status": "string", // 'pristine' | 'in-progress' | 'checked'
  "workspaceHtml": "string", // The user's current, edited HTML content
  "initialGenerationHtml": "string", // The pristine AI-generated HTML, for comparison
  "lastQualityCheck": {
    // Object, null if not yet checked
    "met_criteria": ["string"], // e.g., ["Clarity", "Actionability"]
    "unmet_criteria": ["string"] // e.g., ["Specificity", "Evidence"]
  },
  "lastRefinements": [
    // Array of objects, empty if none generated
    {
      "rationale": "string",
      "revised_snippet": "string"
    }
  ]
}
```

---

## Feature Vector 1: The Guided Assessment Workspace

### Feature 1.1: Interactive & Persistent Assessment Workspace

- **User Story:** As a GRC analyst, I want to generate a baseline assessment, make my own edits, and have my work automatically saved for each control, so that I can switch between tasks or refresh the page without losing my progress during a session.

- **Description of Functionality:**

  1.  When a user selects a control, the application will check `localStorage` for a corresponding state object.
  2.  If state exists, the `workspaceHtml` is loaded into an editable area.
  3.  The assessment display area will be converted into a rich text editor (`contenteditable="true"` `div`).
  4.  Any user edits to the assessment text will automatically update the `workspaceHtml` and `lastModified` fields in the control's `localStorage` object.
  5.  A "Reset" button will allow the user to clear the workspace and the associated `localStorage` entry for that control.

- **Acceptance Criteria:**
  - [ ] When a control is selected, its saved assessment text is correctly loaded from `localStorage`.
  - [ ] User edits in the assessment workspace are persisted in `localStorage` in real-time.
  - [ ] Upon refreshing the page and re-selecting a control, the user's last-edited text is displayed.

### Feature 1.2: Contextual Improvement Snippets

- **User Story:** As a control owner, after writing my assessment, I want the AI to give me 3 specific, clickable suggestions to improve weak areas, so I can instantly upgrade the quality of my documentation.

- **Description of Functionality:**

  1.  A "Refine My Assessment" button appears below the workspace.
  2.  Clicking it sends the current `workspaceHtml` for that control to a backend endpoint.
  3.  The AI analyzes the text and returns 3 targeted improvement suggestions.
  4.  Each suggestion is displayed as a card with a rationale ("Why fix this?") and an "Apply Suggestion" button.
  5.  Clicking "Apply" replaces the relevant portion of the text in the workspace with the AI's improved snippet.

- **Acceptance Criteria:**
  - [ ] The "Refine My Assessment" button successfully calls the backend with the current assessment text.
  - [ ] The backend returns 3 distinct, actionable suggestions.
  - [ ] Suggestions are rendered correctly as cards in the UI.
  - [ ] Clicking "Apply Suggestion" correctly updates the text in the assessment workspace and saves it to `localStorage`.

### Feature 1.3: Qualitative "Quality Rubric" Feedback

- **User Story:** As a GRC analyst, I want to check my assessment against best practices and get clear, actionable feedback on what I've done well and what I still need to fix, so I can confidently improve my work.

- **Description of Functionality:**

  1.  A "Check Quality" button will be available.
  2.  Clicking it sends the current `workspaceHtml` to an analysis endpoint.
  3.  The backend evaluates the text against a pre-defined quality rubric (e.g., Specificity, Clarity, Evidence).
  4.  A status bar appears at the bottom of the screen showing a summary of the check (e.g., "3 of 4 Key Areas Addressed").
  5.  Clicking the status bar opens a modal window displaying a detailed checklist, clearly showing which criteria were met and which need improvement.

- **Implementation Details:**

  - **Data Model:** A `QUALITY_RUBRIC` dictionary will be defined in the backend, mapping criteria names to their descriptions.
  - **Backend (New Endpoint):** `POST /controls/check-quality`
    - **Request Body:** `{ "assessment_text": "<html>...</html>" }`
    - **Logic:** Use a Gemini prompt to evaluate the text against the rubric. The model will return a JSON object classifying each rubric item as "met" or "unmet".
    - **Response Body:** The endpoint will return multiple HTML snippets using HTMX's Out-of-Band Swap feature: one for the status bar and one for the modal's content.
  - **Frontend:**
    - A "Check Quality" button triggers the `hx-post`.
    - HTMX renders the status bar and populates the (initially hidden) modal.
    - A simple JavaScript function handles showing/hiding the modal on click.
    - The quality check results are saved to the `lastQualityCheck` object in `localStorage`.

- **Acceptance Criteria:**
  - [ ] Clicking "Check Quality" triggers a request and displays a status bar at the bottom of the page.
  - [ ] The status bar accurately reflects the number of met vs. total quality criteria.
  - [ ] Clicking the status bar opens a modal window.
  - [ ] The modal correctly displays the checklist of met and unmet criteria.

---

## Feature Vector 2: Centralized Effectiveness Tracking

### Feature 2.1: Co-pilot Interaction Logging for Vertex AI Evaluation

- **User Story:** As a Product Manager, I want to centrally log key user interactions with the AI features, so I can quantitatively measure their helpfulness and make data-driven decisions to improve the co-pilot's underlying models and prompts.

- **Description of Functionality:**
  Key user interactions that signal the usefulness of AI suggestions will be captured on the frontend and sent to a backend tracking endpoint. This endpoint will format the data and log it to the Google Vertex AI Evaluation service for centralized analysis.

- **Trackable Events:**

  - `assessment_generated`: User generates the initial assessment.
  - `refinement_suggestion_applied`: User clicks "Apply Suggestion." **(High-value positive signal)**
  - `quality_check_requested`: User requests a quality rubric check.

- **Implementation Details:**

  - **Backend (New Endpoint):** `POST /track_event`
    - This will be an asynchronous endpoint.
    - **Request Body:** A JSON object with event details (e.g., `event_type`, `control_id`, `state_before`, `state_after`).
    - **Logic:** Formats the payload and logs it to the Vertex AI Evaluation service.
  - **Frontend:** JavaScript functions tied to user actions will send a `fetch` request with the event payload to the `/track_event` endpoint.
  - **Cloud Platform:** An Evaluation Job in the Google Cloud Console will be configured to aggregate these logs and compute metrics like "suggestion acceptance rate."

- **Acceptance Criteria:**
  - [ ] When a user applies a refinement suggestion, a `POST` request is sent to `/track_event` with the correct payload.
  - [ ] When a user requests a quality check, a corresponding event is logged.
  - [ ] Data appears in the configured Vertex AI Evaluation dashboard, allowing for analysis.
