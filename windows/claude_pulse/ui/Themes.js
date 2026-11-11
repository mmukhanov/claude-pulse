.pragma library

// Every themed part reads its colours and fonts from here: popup, panel icon, chart.
var names = ["orbit", "lines", "terminal", "battery", "paper"]

var blue = { a: "#3b82f6", b: "#3b82f6" }
var violet = { a: "#a855f7", b: "#a855f7" }

var themes = {
    orbit: {
        icon: "rings", font: "", radius: 12,
        session: { a: "#22d3ee", b: "#3b82f6" }, week: { a: "#a78bfa", b: "#d946ef" },
        light: { bg: "#f6f7fb", text: "#191c2a", muted: "#696f82", line: "#e0e2ec", card: "#eceef5", danger: "#dc2626" },
        dark: { bg: "#0f1120", text: "#f1f2f9", muted: "#8c91a8", line: "#262a40", card: "#181b2d", danger: "#f87171" }
    },
    lines: {
        icon: "bars", font: "", radius: 8,
        session: blue, week: violet,
        light: { bg: "#ffffff", text: "#1f2430", muted: "#6b7280", line: "#e5e7eb", card: "#f6f7f9", danger: "#dc2626" },
        dark: { bg: "#1f2130", text: "#eceef4", muted: "#9aa0b4", line: "#343748", card: "#282a3b", danger: "#f87171" }
    },
    terminal: {
        icon: "bars", font: "monospace", radius: 2,
        session: { a: "#2563eb", b: "#2563eb" }, week: { a: "#9333ea", b: "#9333ea" },
        light: { bg: "#fbfaf5", text: "#2c2a24", muted: "#7c776a", line: "#d9d5c8", card: "#f3f1e8", danger: "#b91c1c" },
        dark: { bg: "#0d1110", text: "#d7e4d9", muted: "#74877a", line: "#25302a", card: "#141a18", danger: "#f87171" }
    },
    battery: {
        icon: "cells", font: "", radius: 6,
        session: blue, week: violet,
        light: { bg: "#f3f4f6", text: "#111827", muted: "#6b7280", line: "#d8dbe1", card: "#e9ebef", danger: "#dc2626" },
        dark: { bg: "#18191d", text: "#f3f4f6", muted: "#9095a1", line: "#2f3137", card: "#212226", danger: "#f87171" }
    },
    paper: {
        icon: "rings", font: "serif", radius: 10,
        session: { a: "#4f7cac", b: "#4f7cac" }, week: { a: "#8e5ea2", b: "#8e5ea2" },
        light: { bg: "#faf6ee", text: "#2e2720", muted: "#7e7263", line: "#e6dccb", card: "#f3ecdf", danger: "#b4432a" },
        dark: { bg: "#262220", text: "#f4ece0", muted: "#a89a88", line: "#403a35", card: "#2e2a27", danger: "#e8795c" }
    }
}

function tokens(name, dark) {
    var theme = themes[name] || themes.orbit
    var mode = dark ? theme.dark : theme.light
    return {
        name: themes[name] ? name : "orbit", icon: theme.icon, font: theme.font, radius: theme.radius,
        session: theme.session, week: theme.week,
        bg: mode.bg, text: mode.text, muted: mode.muted, line: mode.line, card: mode.card, danger: mode.danger
    }
}

// A window keeps its own colour; only a nearly spent limit turns red.
function limitColors(tk, kind, pct) {
    if (pct >= 85) return { a: tk.danger, b: tk.danger }
    return kind === "week" ? tk.week : tk.session
}

function isDark(mode, systemDark) {
    return mode === "dark" ? true : mode === "light" ? false : systemDark
}
