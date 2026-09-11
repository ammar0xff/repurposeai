/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "oklch(0.10 0 0)",
        surface: "oklch(0.135 0 0)",
        "surface-2": "oklch(0.175 0 0)",
        "surface-3": "oklch(0.215 0 0)",
        ink: "oklch(0.94 0.006 75)",
        body: "oklch(0.88 0.008 75)",
        muted: "oklch(0.70 0.012 75)",
        faint: "oklch(0.52 0.008 75)",
        line: "oklch(1 0 0 / 0.09)",
        "line-2": "oklch(1 0 0 / 0.05)",
        primary: "oklch(0.80 0.14 77)",
        "primary-strong": "oklch(0.865 0.14 78)",
        "primary-ink": "oklch(0.16 0.03 55)",
        "primary-tint": "oklch(0.28 0.07 75 / 0.45)",
        success: "oklch(0.74 0.14 150)",
        "success-tint": "oklch(0.24 0.05 150 / 0.4)",
        danger: "oklch(0.70 0.17 27)",
        "danger-tint": "oklch(0.25 0.07 27 / 0.4)",
        warn: "oklch(0.80 0.13 85)",
        "warn-tint": "oklch(0.26 0.06 85 / 0.4)",
      },
      fontFamily: {
        display: ["Archivo", "ui-sans-serif", "system-ui", "sans-serif"],
        body: ["Archivo", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: [
          "JetBrains Mono",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "monospace",
        ],
      },
      boxShadow: {
        ambient:
          "0 24px 64px -24px rgba(0,0,0,0.55), 0 8px 24px -12px rgba(0,0,0,0.35)",
        "ambient-sm": "0 12px 32px -20px rgba(0,0,0,0.55)",
      },
      borderRadius: {
        lg: "16px",
        xl: "20px",
      },
      transitionTimingFunction: {
        out: "cubic-bezier(0.32, 0.72, 0, 1)",
      },
      keyframes: {
        "pulse-soft": {
          "0%,100%": { opacity: "1" },
          "50%": { opacity: "0.35" },
        },
        shimmer: {
          from: { backgroundPosition: "200% 0" },
          to: { backgroundPosition: "-200% 0" },
        },
        rise: {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        scan: {
          from: { backgroundPosition: "0 0" },
          to: { backgroundPosition: "0 44px" },
        },
      },
      animation: {
        "pulse-soft": "pulse-soft 1.6s ease-in-out infinite",
        shimmer: "shimmer 1.6s linear infinite",
        rise: "rise 0.5s cubic-bezier(0.32, 0.72, 0, 1) both",
        scan: "scan 1.4s linear infinite",
      },
    },
  },
  plugins: [],
};