import QtQuick
import "Themes.js" as Th

// Panel icon in the shape of the current theme: rings, bars or cells.
// Session is always the outer or upper mark, the week the inner or lower one.
Item {
    id: icon

    property var usage: null
    property color textColor: "#eeeeee"
    property color mutedColor: "#aaaaaa"
    property color trackColor: "#40808080"
    property bool showNumbers: true
    property string theme: "orbit"
    property string colorMode: "system"
    property bool systemDark: true

    readonly property var tk: Th.tokens(theme, Th.isDark(colorMode, systemDark))
    readonly property var session: usage ? usage.session : null
    readonly property var week: usage ? usage.week : null
    readonly property real sessionPct: session ? session.pct : 0
    readonly property real weekPct: week ? week.pct : 0
    readonly property bool hasSession: !!session || !week
    readonly property bool critical: sessionPct >= 90 || weekPct >= 90
    readonly property int markSize: Math.max(16, Math.min(height, 32))
    readonly property int markWidth: tk.icon === "rings" ? markSize : markSize * 1.5
    readonly property color sessionColor: Th.limitColors(tk, "session", sessionPct).b
    readonly property color weekColor: Th.limitColors(tk, "week", weekPct).b

    implicitWidth: markWidth + (showNumbers ? 5 + label.implicitWidth + 2 : 0)
    implicitHeight: 24

    Item {
        id: mark
        width: icon.markWidth
        height: icon.markSize
        anchors.verticalCenter: parent.verticalCenter

        Ring {
            visible: icon.tk.icon === "rings" && icon.hasSession
            anchors.fill: parent
            value: icon.sessionPct
            thickness: Math.max(2.5, icon.markSize * 0.13)
            colorA: Th.limitColors(icon.tk, "session", icon.sessionPct).a
            colorB: Th.limitColors(icon.tk, "session", icon.sessionPct).b
            trackColor: icon.trackColor
        }
        Ring {
            visible: icon.tk.icon === "rings"
            anchors.centerIn: parent
            width: parent.height * 0.60
            height: parent.height * 0.60
            value: icon.weekPct
            thickness: Math.max(2.5, icon.markSize * 0.13)
            colorA: Th.limitColors(icon.tk, "week", icon.weekPct).a
            colorB: Th.limitColors(icon.tk, "week", icon.weekPct).b
            trackColor: icon.trackColor
        }

        Column {
            visible: icon.tk.icon !== "rings"
            anchors.centerIn: parent
            width: parent.width
            spacing: Math.max(2, icon.markSize * 0.12)

            Repeater {
                model: icon.hasSession ? [{ pct: icon.sessionPct, color: icon.sessionColor }, { pct: icon.weekPct, color: icon.weekColor }]
                                       : [{ pct: icon.weekPct, color: icon.weekColor }]
                Item {
                    id: strip
                    required property var modelData
                    width: parent.width
                    height: Math.max(4, icon.markSize * 0.28)

                    Rectangle {
                        visible: icon.tk.icon === "bars"
                        anchors.fill: parent
                        radius: Math.min(height / 2, icon.tk.radius)
                        color: icon.trackColor
                        Rectangle {
                            height: parent.height
                            radius: parent.radius
                            width: strip.modelData.pct > 0 ? Math.max(height, parent.width * Math.min(100, strip.modelData.pct) / 100) : 0
                            color: strip.modelData.color
                        }
                    }
                    // Cells show what's left, like a battery.
                    Row {
                        visible: icon.tk.icon === "cells"
                        anchors.fill: parent
                        spacing: 1
                        Repeater {
                            model: 6
                            Rectangle {
                                required property int index
                                width: (strip.width - 5) / 6
                                height: strip.height
                                radius: 1
                                color: index < Math.ceil((100 - strip.modelData.pct) / 100 * 6) ? strip.modelData.color : icon.trackColor
                            }
                        }
                    }
                }
            }
        }

        SequentialAnimation on opacity {
            running: icon.critical
            loops: Animation.Infinite
            alwaysRunToEnd: true
            NumberAnimation { to: 0.45; duration: 900; easing.type: Easing.InOutSine }
            NumberAnimation { to: 1; duration: 900; easing.type: Easing.InOutSine }
        }
    }

    // Orange badge: at this pace a limit runs out before it resets.
    Rectangle {
        visible: !!((icon.session && icon.session.runout) || (icon.week && icon.week.runout))
        width: Math.max(6, icon.markSize * 0.3)
        height: width
        radius: width / 2
        color: "#f97316"
        border.color: icon.textColor
        border.width: 1
        anchors.right: mark.right
        anchors.top: mark.top
    }

    Row {
        id: label
        visible: icon.showNumbers
        anchors.left: mark.right
        anchors.leftMargin: 5
        anchors.verticalCenter: parent.verticalCenter
        spacing: 4
        T {
            visible: icon.hasSession
            tk: icon.tk
            text: icon.session ? Math.round(icon.sessionPct) + "%" : "—"
            color: icon.textColor
            font.pixelSize: Math.min(13, Math.max(10, icon.height * 0.48))
            font.weight: Font.DemiBold
        }
        T {
            visible: !!icon.week
            tk: icon.tk
            text: Math.round(icon.weekPct) + "%"
            color: icon.mutedColor
            font.pixelSize: Math.min(13, Math.max(10, icon.height * 0.48))
        }
    }
}
