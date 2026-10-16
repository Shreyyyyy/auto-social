/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {sans: ["var(--font-sans)", "system-ui", "sans-serif"], display: ["var(--font-display)", "var(--font-sans)", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"]},
      // "case" is the app's accent everywhere: neon violet, with cyan + magenta as partners
      colors: {case: {50: "#f3efff", 400: "#a78bfa", 500: "#7c3aed", 600: "#6d28d9"}, neon: {cyan: "#22d3ee", violet: "#8b5cf6", pink: "#f472b6"}, cork: "#22d3ee"},
      keyframes: {
        shimmer: {"0%": {backgroundPosition: "0% 50%"}, "100%": {backgroundPosition: "200% 50%"}},
        spin_slow: {to: {transform: "rotate(360deg)"}},
        float: {"0%,100%": {transform: "translateY(0)"}, "50%": {transform: "translateY(-6px)"}},
        rise: {from: {opacity: "0", transform: "translateY(12px)"}, to: {opacity: "1", transform: "none"}},
      },
      animation: {shimmer: "shimmer 4s linear infinite", "spin-slow": "spin_slow 6s linear infinite", float: "float 5s ease-in-out infinite",
        rise: "rise .6s cubic-bezier(.2,.8,.2,1) both"},
    },
  },
  plugins: [],
};
