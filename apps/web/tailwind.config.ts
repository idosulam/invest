import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        primary: { 50: "#eff6ff", 100: "#dbeafe", 200: "#bfdbfe", 300: "#93c5fd", 400: "#60a5fa", 500: "#3b82f6", 600: "#2563eb", 700: "#1d4ed8", 800: "#1e40af", 900: "#1e3a8a" },
        success: { 500: "#22c55e", 600: "#16a34a" },
        danger: { 500: "#ef4444", 600: "#dc2626" },
        warning: { 500: "#f59e0b", 600: "#d97706" },
        surface: { 50: "#f8fafc", 100: "#f1f5f9", 200: "#e2e8f0", 700: "#334155", 800: "#1e293b", 900: "#0f172a" },
      },
    },
  },
  plugins: [],
};

export default config;
