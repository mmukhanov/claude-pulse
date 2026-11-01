#!/bin/sh
# Installs or updates Claude Pulse for the current user. No root needed.
#   ./install.sh            pick the Plasma widget on Plasma 6, otherwise the tray app
#   ./install.sh --plasma   Plasma 6 widget
#   ./install.sh --tray     tray app for other desktops (needs PyQt6)
#   ./install.sh --no-panel with --plasma: don't add the widget to a panel
set -eu
cd "$(dirname "$0")"

mode=auto
panel=yes
for arg in "$@"; do
    case "$arg" in
        --plasma) mode=plasma ;;
        --tray) mode=tray ;;
        --no-panel) panel=no ;;
        *) echo "Unknown option: $arg" >&2; exit 2 ;;
    esac
done

if [ "$mode" = auto ]; then
    case "${XDG_CURRENT_DESKTOP:-}" in
        *KDE*) command -v kpackagetool6 >/dev/null 2>&1 && mode=plasma || mode=tray ;;
        *) mode=tray ;;
    esac
fi

command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 1; }
command -v claude >/dev/null 2>&1 || [ -x "$HOME/.local/bin/claude" ] ||
    echo "Warning: claude was not found. Install Claude Code and log in with a subscription." >&2

if [ "$mode" = plasma ]; then
    if kpackagetool6 -t Plasma/Applet -l 2>/dev/null | grep -qx claudepulse; then
        kpackagetool6 -t Plasma/Applet -u package
        echo "Updated. Restart the shell to load it: systemctl --user restart plasma-plasmashell"
    else
        kpackagetool6 -t Plasma/Applet -i package
    fi
    if [ "$panel" = yes ] && command -v qdbus6 >/dev/null 2>&1; then
        qdbus6 org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript '
            var found = false;
            panels().forEach(function (p) {
                p.widgetIds.forEach(function (id) {
                    if (p.widgetById(id).type === "claudepulse") found = true;
                });
            });
            if (!found && panels().length > 0) panels()[0].addWidget("claudepulse");
        ' >/dev/null || echo "Could not reach Plasma. Add the widget by hand: right-click the panel, Add Widgets, Claude Pulse."
    fi
else
    python3 -c 'import PyQt6.QtQuick, PyQt6.QtWidgets' 2>/dev/null ||
        { echo "The tray app needs PyQt6 and its QML modules. See README.md." >&2; exit 1; }
    data="${XDG_DATA_HOME:-$HOME/.local/share}/claude-pulse"
    autostart="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
    mkdir -p "$data" "$autostart"
    rm -rf "$data/package"
    cp -R package "$data/package"
    cat > "$autostart/claude-pulse.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Claude Pulse
Comment=Claude Code usage in the tray
Exec=python3 "$data/package/contents/code/tray.py"
Icon=utilities-system-monitor
X-GNOME-Autostart-enabled=true
EOF
    nohup python3 "$data/package/contents/code/tray.py" >/dev/null 2>&1 &
    echo "Installed. The tray icon starts now and at every login."
fi
