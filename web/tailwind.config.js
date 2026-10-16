/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {sans: ["var(--font-sans)", "system-ui", "sans-serif"], mono: ["var(--font-mono)", "ui-monospace", "monospace"]},
      colors: {case: {50: "#fdf6ee", 400: "#e2574c", 500: "#c8231b", 600: "#a51b14"}, cork: "#b48655"},
    },
  },
  plugins: [],
};
