import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0B0F14",
        panel: "#121821",
        border: "#1F2A37",
        text: "#E6EDF3",
        muted: "#8B98A5",
        risk: {
          low: "#22C55E",
          medium: "#EAB308",
          high: "#F97316",
          critical: "#EF4444",
        },
        accent: "#38BDF8",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },
      fontSize: {
        xs: ["0.875rem", "1.25rem"],
      },
    },
  },
  plugins: [],
} satisfies Config;
