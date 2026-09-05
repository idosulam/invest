import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        primary: { 50: "#eff6ff", 100: "#dbeafe", 200: "#bfdbfe", 300: "#93c5fd", 400: "#60a5fa", 500: "#3b82f6", 600: "#2563eb", 700: "#1d4ed8", 800: "#1e40af", 900: "#1e3a8a" },
        success: { 50: "#052e16", 500: "#22c55e", 600: "#16a34a" },
        danger: { 50: "#450a0a", 500: "#ef4444", 600: "#dc2626" },
        warning: { 50: "#451a03", 500: "#f59e0b", 600: "#d97706" },
        surface: {
          50: "#f8fafc",
          100: "#1f2937",
          200: "#374151",
          300: "#4b5563",
          400: "#9ca3af",
          500: "#d1d5db",
          600: "#e5e7eb",
          700: "#374151",
          800: "#111827",
          900: "#030712",
        },
      },
    },
  },
  plugins: [],
};

export default config;
