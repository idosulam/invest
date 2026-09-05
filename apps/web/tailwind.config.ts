import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        // Primary — Electric blue for interactive elements, data highlights
        primary: {
          50: "#eff6ff",
          100: "#dbeafe",
          200: "#bfdbfe",
          300: "#93c5fd",
          400: "#60a5fa",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
          800: "#1e40af",
          900: "#1e3a8a",
        },
        // Semantic — muted, not neon
        success: { 50: "#052e16", 400: "#4ade80", 500: "#22c55e", 600: "#16a34a" },
        danger: { 50: "#450a0a", 400: "#f87171", 500: "#ef4444", 600: "#dc2626" },
        warning: { 50: "#451a03", 400: "#fbbf24", 500: "#f59e0b", 600: "#d97706" },
        // Surface — deliberate dark scale for financial UI
        // Darker numbers = darker surfaces (backgrounds, containers)
        // Lighter numbers = lighter surfaces (text, borders on dark)
        surface: {
          50: "#020617",   // Deepest — page background
          100: "#0f172a",  // Card/panel background
          200: "#1e293b",  // Elevated surfaces, hover states
          300: "#334155",  // Borders, dividers
          400: "#64748b",  // Muted text, placeholders
          500: "#94a3b8",  // Secondary text
          600: "#cbd5e1",  // Primary body text
          700: "#e2e8f0",  // Emphasized text, headings
          800: "#f1f5f9",  // Bright text, strong emphasis
          900: "#ffffff",  // Maximum contrast
        },
      },
      fontFamily: {
        sans: ['"Inter"', "system-ui", "-apple-system", "sans-serif"],
        mono: ['"JetBrains Mono"', '"Fira Code"', "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
