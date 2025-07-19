Of course. This is the perfect way to approach a project like this: define the absolute Minimum Viable Product (MVP) that delivers value quickly and provides a foundation for future iteration.

Here is the functional specification for version 0.1, rewritten from the ground up with a focus on speed of development and a detailed, step-by-step implementation plan.

---

# Functional Specification: GRC Co-pilot v0.1 - The Core Assistant MVP

**Version:** 0.1  
**Author:** Product Manager

## 1. Product Vision & Goals

Version 0.1 is the foundational MVP of the GRC Co-pilot. We assume our users are skilled professionals who prefer to write their own assessments. Our goal is to augment, not replace, their manual workflow by providing targeted AI tools that solve their most tedious tasks with one-click simplicity.

This version prioritizes speed of development and immediate user value. The features are designed to be implemented quickly using the existing FastAPI and HTMX stack, with all user-facing state managed exclusively in `localStorage`. This will provide a stable, useful tool and a rich data stream for evaluating its effectiveness.

## 2. Core Features for v0.1

### Feature 1: The Structured Assessment Workspace

- **User Story:** As an analyst, I want a simple, structured form for each control to organize my thoughts and ensure I don't miss key sections. My work must be saved automatically so I don't lose it.
- **Description:** The main content area is a simple HTML form with three `textarea` fields:
  1.  Control Operation
  2.  Design & Implementation Details
  3.  Evidence Description
- **Persistence:** All text entered is automatically saved to `localStorage`. The data is keyed by control and field, e.g., `grc-AC-02-evidence_description`.

### Feature 2: One-Click "AI Polish"

- **User Story:** My initial notes are rough. I want a one-click way to transform them into professional, audit-ready language for any section I'm working on.
- **Description:** A "Polish" button is placed next to each `textarea`. Clicking it sends the current text to the backend and instantly replaces it with a professionally rephrased version.

### Feature 3: AI-Powered Evidence Summarizer

- **User Story:** I struggle to write formal descriptions for my evidence (like screenshots). I want to just describe what the evidence is and have the AI write the auditable summary for me.
- **Description:** A simple, self-contained "Evidence Helper" tool on the page. It has one input field and a "Summarize Evidence" button. The user types a hint, clicks the button, and receives a formal summary snippet they can copy and paste.

### Supporting Feature: Effectiveness Tracking

- **Goal:** To lay the foundation for Feature Vector 2 by logging every meaningful AI interaction to a backend endpoint. This data is critical for measuring the value of our features.

## 3. Step-by-Step MVP Implementation Plan

This plan is ordered to build foundational features first, ensuring each step results in a testable and incrementally more valuable application.

---

### **Step 1: Build the Foundation - The Structured Workspace UI**

**Goal:** Replace the current generic detail view with the structured `textarea` form.

- **Backend Tasks:**
  - Modify the main control detail endpoint (e.g., `GET /controls/{control_id}`).
  - Ensure it uses a Jinja2 template (`templates/control_detail.html`) that contains the new form structure.
- **Frontend Tasks (HTML/Templates):**
  - Create `templates/control_detail.html`.
  - Inside, design the form with three labeled `textarea` elements.
  - **Crucially, give each `textarea` a predictable `id`** that includes the control ID, so it can be targeted by JavaScript and HTMX.
    - _Example:_ `<textarea id="control-op-{{ control.id }}">...</textarea>`

---

### **Step 2: Make it Usable - Session Persistence with `localStorage`**

**Goal:** Ensure any text typed by the user is not lost when they switch controls or refresh the page.

- **Backend Tasks:** None. This is a purely client-side feature.
- **Frontend Tasks (JavaScript):**
  - Write a small block of vanilla JavaScript in your main template.
  - **On Save:** Attach an `oninput` event listener to each `textarea`. When the user types, this function saves the content to `localStorage`.
    - _Example Key:_ `localStorage.setItem(`grc-${control.id}-control-op`, event.target.value);`
  - **On Load:** When the control detail page loads, the script must read from `localStorage` for each field and populate the `textarea`s if data exists.

---

### **Step 3: Add the First "Magic" - The "AI Polish" Feature**

**Goal:** Implement the one-click text polishing feature.

- **Backend Tasks:**
  - Create a new FastAPI endpoint: `POST /ai/polish-text`.
  - This endpoint accepts a single form field: `text: str = Form(...)`.
  - **Prompt Engineering:** Implement the AI call. The prompt should be simple: _"Act as an expert GRC analyst. Rephrase the following text to be clear, concise, and professional for an audit report. Do not add new information. Text: [user's text]"_
  - The endpoint returns the polished text as a simple `HTMLResponse`.
- **Frontend Tasks (HTMX):**
  - Add a "Polish" button next to each `textarea`.
  - Configure the button with HTMX attributes to call the new endpoint. The key is using `hx-swap="value"` to directly update the `textarea`.
    ```html
    <textarea id="control-op-{{ control.id }}"></textarea>
    <button
      hx-post="/ai/polish-text"
      hx-vals='{"text": document.getElementById("control-op-{{ control.id }}").value}'
      hx-target="#control-op-{{ control.id }}"
      hx-swap="value"
      class="polish-button"
      data-section="Control Operation"
      data-control-id="{{ control.id }}"
    >
      Polish
    </button>
    ```

---

### **Step 4: Add the Second Tool - The Evidence Summarizer**

**Goal:** Implement the self-contained evidence helper tool.

- **Backend Tasks:**
  - Create another new endpoint: `POST /ai/summarize-evidence`.
  - It accepts one form field: `hint: str = Form(...)`.
  - **Prompt Engineering:** _"You are an IT auditor. Convert the following hint about a piece of evidence into a formal sentence for an audit report. Hint: [user's hint]"_
  - The endpoint returns the generated summary wrapped in a simple HTML `div` with a "Copy" button.
- **Frontend Tasks (HTMX):**
  - Add the "Evidence Helper" HTML structure to your main template. It needs an input field, a button, and a target `div` for the result.
    ```html
    <h4>Evidence Helper</h4>
    <input
      type="text"
      id="evidence-hint-input"
      placeholder="e.g., screenshot of user list"
    />
    <button
      hx-post="/ai/summarize-evidence"
      hx-vals='{"hint": document.getElementById("evidence-hint-input").value}'
      hx-target="#evidence-summary-result"
      id="summarize-btn"
      data-control-id="{{ control.id }}"
    >
      Summarize Evidence
    </button>
    <div id="evidence-summary-result"></div>
    ```

---

### **Step 5: Build the Business Foundation - Effectiveness Tracking**

**Goal:** Create the logging endpoint and hook up the existing features to send data.

- **Backend Tasks:**
  - Create the final endpoint: `POST /track_event`. This should be an `async` function.
  - It will accept a Pydantic model representing the event payload. For v0.1, it can just accept a `dict`.
  - The function's only job is to print the received log to the console for now (e.g., `print(f"TRACKING EVENT: {event_data}")`). This validates the mechanism before integrating with Vertex AI.
- **Frontend Tasks (JavaScript):**
  - Add a new JavaScript function `trackEvent(payload)`. This function will use `fetch` to `POST` the JSON payload to `/track_event`.
  - Modify the event listeners for the "Polish" and "Summarize" buttons. Use the `htmx:afterOnLoad` event to trigger the tracking call _after_ the AI response has been successfully loaded.
  - **Example Payload for Polish:**
    ```javascript
    // In your HTMX event listener for the polish button...
    const payload = {
      event_type: "text_polished",
      control_id: button.dataset.controlId,
      context: {
        section: button.dataset.section,
        text_before: originalText, // You'll need to store this before the swap
        text_after: event.detail.xhr.responseText,
      },
    };
    trackEvent(payload);
    ```

By following this five-step plan, we can rapidly develop a highly valuable MVP that directly assists users in their core tasks, all while building the essential data foundation for future, more advanced features.
