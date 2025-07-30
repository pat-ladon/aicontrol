// static/js/workspace.js

// --- Core State Management ---
const getWorkspaceState = (controlId) => {
  const state = localStorage.getItem(`grc-copilot-assessment-${controlId}`);
  return state ? JSON.parse(state) : null;
};

const saveWorkspaceState = (controlId, state) => {
  state.lastModified = new Date().toISOString();
  localStorage.setItem(
    `grc-copilot-assessment-${controlId}`,
    JSON.stringify(state)
  );
};

const createInitialState = (controlId, initialHtml) => {
  return {
    controlId: controlId,
    lastModified: new Date().toISOString(),
    status: "pristine",
    workspaceHtml: initialHtml,
    initialGenerationHtml: initialHtml,
    lastQualityCheck: null,
    lastRefinements: [],
  };
};

// --- UI Interaction Functions ---
function initializeWorkspace(controlId) {
  const workspace = document.getElementById("assessment-workspace");
  if (!workspace) return;

  // Load saved state or generate initial state
  let state = getWorkspaceState(controlId);
  if (state && state.workspaceHtml) {
    workspace.innerHTML = state.workspaceHtml;
  } else {
    // This assumes the initial AI-generated content is already in the div
    const initialHtml = workspace.innerHTML;
    state = createInitialState(controlId, initialHtml);
    saveWorkspaceState(controlId, state);
  }

  // Make it editable and save on change
  workspace.setAttribute("contenteditable", "true");
  workspace.addEventListener("input", () => {
    state.status = "in-progress";
    state.workspaceHtml = workspace.innerHTML;
    saveWorkspaceState(controlId, state);
  });
}

function resetWorkspace(controlId) {
  localStorage.removeItem(`grc-copilot-assessment-${controlId}`);
  // Trigger HTMX to reload the original control details
  htmx.trigger(`#control-row-${controlId}`, "click");
}

// Attach functions to the global window object to be callable from HTML
window.grc = {
  initializeWorkspace,
  resetWorkspace,
};

// Add this new tracking function
// The "Apply" button in the refinement card template calls this function.
const trackEvent = (eventType, controlId, details = {}) => {
  const payload = {
    event_type: eventType,
    control_id: controlId,
    ...details,
  };

  fetch("/track_event", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
};
