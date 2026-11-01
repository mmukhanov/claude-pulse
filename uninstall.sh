#!/bin/sh
# Removes Claude Pulse. --purge also deletes its settings and history.
set -u

if command -v qdbus6 >/dev/null 2>&1; then
    qdbus6 org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript '
        panels().forEach(function (p) {
            p.widgetIds.forEach(function (id) {
                var w = p.widgetById(id);
                if (w.type === "claudepulse") w.remove();
            });
        });
    ' >/dev/null 2>&1
fi
if command -v kpackagetool6 >/dev/null 2>&1; then
    kpackagetool6 -t Plasma/Applet -r claudepulse >/dev/null 2>&1
fi

pkill -f "claude-pulse/package/contents/code/tray.py" 2>/dev/null
rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/claude-pulse.desktop"
rm -rf "${XDG_DATA_HOME:-$HOME/.local/share}/claude-pulse"

if [ "${1:-}" = "--purge" ]; then
    rm -rf "${XDG_STATE_HOME:-$HOME/.local/state}/claude-pulse" "${XDG_CONFIG_HOME:-$HOME/.config}/claude-pulse"
fi
echo "Claude Pulse removed."
