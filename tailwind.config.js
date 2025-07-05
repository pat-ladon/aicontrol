/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/**/*.{html,jinja}"],
  darkMode: "selector", // Uses data-theme attribute
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#E6F0FA", // Light mode: Very light blue for backgrounds
          100: "#BFDBFE",
          200: "#93C5FD",
          300: "#60A5FA",
          400: "#3B82F6",
          500: "#1E3A8A", // Light mode: Primary blue for headers/buttons
          600: "#1E40AF",
          700: "#1E3A8A", // Dark mode: Primary blue
          800: "#1E3A8A",
          900: "#1E3A8A",
        },
        secondary: {
          50: "#F9FAFB", // Light mode: Light gray for backgrounds
          100: "#F3F4F6",
          200: "#E5E7EB",
          300: "#D1D5DB",
          400: "#9CA3AF",
          500: "#6B7280",
          600: "#4B5563",
          700: "#374151", // Dark mode: Dark gray for backgrounds
          800: "#1F2A44",
          900: "#111827",
        },
        accent: {
          50: "#ECFDF5",
          100: "#D1FAE5",
          200: "#A7F3D0",
          300: "#6EE7B7",
          400: "#34D399",
          500: "#10B981", // Teal for highlights
          600: "#059669",
          700: "#047857",
          800: "#065F46",
          900: "#064E3B",
        },
        neutral: {
          50: "#FAFAFA",
          100: "#F5F5F5",
          200: "#E5E5E5",
          300: "#D4D4D4",
          400: "#A3A3A3",
          500: "#737373",
          600: "#525252",
          700: "#404040",
          800: "#262626",
          900: "#171717", // Light mode: Text, Dark mode: Background
          950: "#0A0A0A",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
      fontSize: {
        xs: ["0.75rem", { lineHeight: "1rem" }],
        sm: ["0.875rem", { lineHeight: "1.25rem" }],
        base: ["1rem", { lineHeight: "1.5rem" }],
        lg: ["1.125rem", { lineHeight: "1.75rem" }],
        xl: ["1.25rem", { lineHeight: "1.75rem" }],
        "2xl": ["1.5rem", { lineHeight: "2rem" }],
      },
      spacing: {
        18: "4.5rem",
        112: "28rem",
        128: "32rem",
      },
      borderRadius: {
        xl: "1rem",
        "2xl": "1.5rem",
      },
      boxShadow: {
        soft: "0 2px 15px -3px rgba(0, 0, 0, 0.07), 0 10px 20px -2px rgba(0, 0, 0, 0.04)",
      },
    },
  },
  plugins: [],
};
