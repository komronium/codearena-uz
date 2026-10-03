/** Tailwind v3, the same line the Play CDN served. Colors are CSS variables (see
 * src/app.css) so light/dark themes switch without rebuilding. */
module.exports = {
  // Relative to frontend/ (the build runs here). Python files carry widget classes.
  content: ["../templates/**/*.html", "../apps/**/*.py"],
  theme: {
    extend: {
      colors: {
        paper: "rgb(var(--ca-paper-rgb) / <alpha-value>)",
        ink: "rgb(var(--ca-ink-rgb) / <alpha-value>)",
        mute: "rgb(var(--ca-mute-rgb) / <alpha-value>)",
        line: "rgb(var(--ca-line-rgb) / <alpha-value>)",
        surface: "rgb(var(--ca-surface-rgb) / <alpha-value>)",
        sunk: "rgb(var(--ca-sunk-rgb) / <alpha-value>)",
        gold: "rgb(var(--ca-gold-rgb) / <alpha-value>)",
        accent: {
          DEFAULT: "rgb(var(--ca-accent-rgb) / <alpha-value>)",
          hover: "rgb(var(--ca-accent-hover-rgb) / <alpha-value>)",
          soft: "rgb(var(--ca-accent-rgb) / .1)",
        },
        ok: { DEFAULT: "rgb(var(--ca-ok-rgb) / <alpha-value>)", soft: "rgb(var(--ca-ok-rgb) / .12)" },
        bad: { DEFAULT: "rgb(var(--ca-bad-rgb) / <alpha-value>)", soft: "rgb(var(--ca-bad-rgb) / .12)" },
        warn: { DEFAULT: "rgb(var(--ca-warn-rgb) / <alpha-value>)", soft: "rgb(var(--ca-warn-rgb) / .12)" },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
    },
  },
};
