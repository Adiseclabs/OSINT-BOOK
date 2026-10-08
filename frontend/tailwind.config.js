/** Palette: graphite surfaces, one steel accent; amber is reserved for *uncertainty*, red for failure. */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    borderRadius: { none: "0", sm: "2px", DEFAULT: "2px", md: "3px", full: "9999px" },
    extend: {
      colors: Object.fromEntries(["bg", "panel", "raised", "line", "ink", "mute", "accent", "warn", "bad", "ok"].map((k) => [k, `rgb(var(--${k}) / <alpha-value>)`])),
      fontFamily: { sans: ['"IBM Plex Sans"', '"Segoe UI"', "system-ui", "sans-serif"], mono: ['"IBM Plex Mono"', "ui-monospace", "Consolas", "monospace"] },
      fontSize: { xs: ["11.5px", "16px"], sm: ["12.5px", "18px"], base: ["13.5px", "20px"] },
    },
  },
  plugins: [],
};
