/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Black & white neumorphism palette.
        bg: "#0a0a0a",
        surface: "#111111",
        surface2: "#161616",
        rim: "#1f1f1f",
        line: "#262626",
        ink: "#f5f5f5",
        ink2: "#cfcfcf",
        muted: "#7c7c7c",
        accent: "#ffffff",
        danger: "#f87171",
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "monospace",
        ],
      },
      boxShadow: {
        // Neumorphism: paired light/dark shadows on a near-black surface.
        neu: "8px 8px 18px rgba(0, 0, 0, 0.65), -6px -6px 14px rgba(60, 60, 60, 0.10)",
        "neu-sm": "5px 5px 10px rgba(0,0,0,0.6), -3px -3px 8px rgba(60,60,60,0.08)",
        "neu-pressed":
          "inset 6px 6px 14px rgba(0,0,0,0.7), inset -4px -4px 10px rgba(80,80,80,0.10)",
        "neu-inset":
          "inset 4px 4px 10px rgba(0,0,0,0.55), inset -2px -2px 6px rgba(70,70,70,0.10)",
      },
    },
  },
  plugins: [],
};
