// --- START OF FILE theme.js (Corrected) ---

document.addEventListener("DOMContentLoaded", () => {
  const html = document.documentElement;
  const toggle = document.getElementById("theme-toggle");

  // A function to update the button text based on the current theme
  const updateToggleButton = () => {
    if (html.classList.contains("dark")) {
      toggle.textContent = "☀ Light";
    } else {
      toggle.textContent = "🌙 Dark";
    }
  };

  // On page load, check localStorage and apply the 'dark' class if needed
  if (localStorage.getItem("theme") === "dark") {
    html.classList.add("dark");
  }

  // Set the initial button text
  updateToggleButton();

  // Toggle theme on click
  toggle.addEventListener("click", () => {
    // Toggle the .dark class on the <html> element
    html.classList.toggle("dark");

    // Save the new theme state to localStorage
    if (html.classList.contains("dark")) {
      localStorage.setItem("theme", "dark");
    } else {
      localStorage.setItem("theme", "light");
    }

    // Update the button text
    updateToggleButton();
  });
});
