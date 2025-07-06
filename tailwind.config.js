// tailwind.config.js

module.exports = {
  content: ["./templates/**/*.html", "./templates/partials/**/*.html"],
  darkMode: "class",

  theme: {
    // We define our entire color palette here, completely REPLACING the default.
    // It is NOT inside the 'extend' block.
    colors: {
      // Add transparent and current for utility
      transparent: "transparent",
      current: "currentColor",
      // Primary Action Colors
      primary: {
        500: "#0A2540", // Deep Navy
        600: "#28A7A7", // Action Teal
      },
      // UI Shades Palette
      secondary: {
        50: "#F8F9FA", // Light Mode: Page BG
        100: "#FFFFFF", // Light Mode: Card/Surface BG
        200: "#E9ECEF", // Light Mode: Borders
        300: "#F1F3F5", // Light Mode: Subtle Hover State
        700: "#3A5983", // Dark Mode: Borders
        800: "#0A2540", // Dark Mode: Page BG
        850: "#1E3A5F", // Dark Mode: Card/Surface BG
        900: "#2A4B7C", // Dark Mode: Hover State
      },
      // Accent & Neutral Text Colors
      accent: {
        500: "#28A7A7",
        600: "#1e7777",
      },
      neutral: {
        50: "#F8F9FA", // Text on Dark BG
        100: "#F8F9FA", // Dark Mode Primary Text
        900: "#0A2540", // Light Mode Primary Text
      },
      // Utility Colors
      white: "#FFFFFF",
      gray: {
        400: "#9ca3af",
        500: "#6b7280",
        600: "#4b5563",
        800: "#1f2937",
      },
    },
    // The 'extend' block is now used for non-color extensions if needed.
    extend: {
      // You can extend fonts, spacing, etc. here later.
    },
  },

  plugins: [require("@tailwindcss/typography")],
};
