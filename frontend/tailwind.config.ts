import type { Config } from "tailwindcss";

/**
 * Design tokens for the dispatch console.
 * Cool paper + cobalt signal + condensed board type. Priority is the only
 * place saturated colour is allowed, so urgency reads at a glance.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#E7EAF1",
        card: "#FFFFFF",
        ink: "#0F1319",
        muted: "#6B7385",
        rule: "#CFD5E2",
        signal: "#2A3FD4",
        "signal-wash": "#EDF0FF",
        critical: "#C31F45",
        high: "#D2760B",
        medium: "#3E7CB1",
        low: "#7C8698",
        ok: "#1B7F62",
      },
      fontFamily: {
        board: ["'IBM Plex Sans Condensed'", "system-ui", "sans-serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["'IBM Plex Mono'", "ui-monospace", "monospace"],
      },
      fontSize: {
        eyebrow: ["0.6875rem", { lineHeight: "1", letterSpacing: "0.14em" }],
      },
      borderRadius: { card: "3px" },
      boxShadow: {
        card: "0 1px 0 rgba(15,19,25,.05), 0 1px 3px rgba(15,19,25,.06)",
        lift: "0 2px 0 rgba(15,19,25,.06), 0 8px 24px rgba(15,19,25,.10)",
      },
      keyframes: {
        tick: { "0%": { transform: "scaleY(0)" }, "100%": { transform: "scaleY(1)" } },
        slide: { "0%": { opacity: "0", transform: "translateY(6px)" }, "100%": { opacity: "1", transform: "none" } },
      },
      animation: {
        tick: "tick .45s cubic-bezier(.2,.9,.3,1) both",
        slide: "slide .35s ease both",
      },
    },
  },
  plugins: [],
};
export default config;
