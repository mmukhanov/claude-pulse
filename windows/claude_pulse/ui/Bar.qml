import QtQuick
import "Themes.js" as Th

// One limit as a bar with a pace tick. Styles: "bar", "cells" (shows what's left), "text".
Item {
    id: bar

    property var tk
    property string kind: "session"
    property string style: "bar"
    property real pct: 0
    property real pace: -1
    property int thickness: 7

    readonly property var colors: Th.limitColors(tk, kind, pct)
    readonly property int count: 20
    readonly property int chars: Math.max(10, Math.floor(width / Math.max(1, metrics.advanceWidth)))

    implicitHeight: style === "cells" ? 18 : style === "text" ? blocks.implicitHeight : thickness

    function blockText() {
        var filled = Math.round(pct / 100 * chars), out = ""
        var tick = pace >= 0 ? Math.min(chars - 1, Math.round(pace / 100 * chars)) : -1
        for (var i = 0; i < chars; i++)
            out += i === tick ? "|" : (i < filled ? "█" : "░")
        return out
    }

    Rectangle {
        visible: bar.style === "bar"
        anchors.fill: parent
        radius: Math.min(height / 2, bar.tk.radius)
        color: bar.tk.line
        Rectangle {
            height: parent.height
            radius: parent.radius
            width: bar.pct > 0 ? Math.max(height, parent.width * Math.min(100, bar.pct) / 100) : 0
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: bar.colors.a }
                GradientStop { position: 1; color: bar.colors.b }
            }
            Behavior on width { NumberAnimation { duration: 900; easing.type: Easing.OutCubic } }
        }
    }

    Row {
        visible: bar.style === "cells"
        anchors.fill: parent
        spacing: 2
        Repeater {
            model: bar.style === "cells" ? bar.count : 0
            Rectangle {
                required property int index
                width: (bar.width - (bar.count - 1) * 2) / bar.count
                height: parent.height
                radius: Math.min(2, bar.tk.radius)
                color: index < Math.round((100 - bar.pct) / 100 * bar.count) ? bar.colors.b : bar.tk.line
                Behavior on color { ColorAnimation { duration: 400 } }
            }
        }
    }

    TextMetrics {
        id: metrics
        font: blocks.font
        text: "█"
    }

    T {
        id: blocks
        visible: bar.style === "text"
        tk: bar.tk
        text: bar.style === "text" ? bar.blockText() : ""
        color: bar.colors.b
        font.pixelSize: 12
        width: parent.width
        clip: true
    }

    Rectangle {
        visible: bar.pace >= 0 && bar.style !== "text"
        x: Math.min(bar.width - width, bar.width * bar.pace / 100)
        y: -2
        width: 2
        height: bar.height + 4
        radius: 1
        color: bar.tk.text
    }
}
