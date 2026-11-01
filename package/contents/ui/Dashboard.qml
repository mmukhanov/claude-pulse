import QtQuick
import QtQuick.Layouts
import "Palette.js" as P
import "Themes.js" as Th

// The popup. Plain QtQuick with the theme passed in, so the Plasma widget and the
// tray app look the same. Only the middle part differs from theme to theme.
Item {
    id: board

    property var usage: null
    property bool busy: false
    property real now: Date.now() / 1000
    property string theme: "orbit"
    property string colorMode: "system"
    property bool systemDark: true
    property real bleed: 0
    signal refreshRequested()

    readonly property bool dark: Th.isDark(colorMode, systemDark)
    readonly property var tk: Th.tokens(theme, dark)
    readonly property var session: usage ? usage.session : null
    readonly property var week: usage ? usage.week : null
    readonly property var verdict: makeVerdict()
    readonly property var days: dayLabels()

    implicitWidth: 420
    implicitHeight: column.implicitHeight + 32

    function missingText(kind) {
        return kind === "session" && week ? P.t("No 5-hour limit") : P.t("No data")
    }

    function resetText(limit) {
        if (!limit || !limit.reset) return ""
        var left = limit.reset - now
        return left < 86400 ? P.t("resets in %1", P.duration(left)) : P.t("resets %1", P.clock(limit.reset, now))
    }

    function makeVerdict() {
        if (!usage || (!session && !week))
            return { color: "#94a3b8", title: P.t("No data"),
                     text: usage && usage.error ? P.t(usage.error) : P.t("Waiting for the first answer from Claude Code") }
        var hard = (session && session.pct >= 100) ? session : (week && week.pct >= 100 ? week : null)
        if (hard) {
            var what = P.t(hard === session ? "Session limit reached" : "Week limit reached")
            return { color: tk.danger, title: P.t("Limit reached"),
                     text: hard.reset ? P.t("%1, resets in %2", what, P.duration(hard.reset - now)) : what }
        }
        var sRun = session && session.runout, wRun = week && week.runout
        if (sRun || wRun) {
            // Warn about whichever window ends the work first.
            var first = sRun && (!wRun || session.runout <= week.runout)
            var w = first ? session : week
            return { color: "#f97316", title: P.t("Using it faster than the pace"),
                     text: P.t(first ? "Session: at this pace it runs out at %1, %2 before the reset"
                                     : "Week: at this pace it runs out at %1, %2 before the reset",
                               P.clock(w.runout, now), P.duration(w.reset - w.runout)) }
        }
        var sp = session ? session.projected : -1, wp = week ? week.projected : -1
        var projected = Math.max(sp, wp)
        if (projected < 0)
            return { color: "#34d399", title: P.t("All clear"), text: P.t("Windows just started, forecast comes later") }
        return { color: projected >= 75 ? "#fbbf24" : "#34d399",
                 title: P.t(projected >= 75 ? "Enough, but tight" : "All clear"),
                 text: P.t(sp >= wp ? "Session: about %1% of the limit by the reset" : "Week: about %1% of the limit by the reset",
                           Math.round(projected)) }
    }

    function statLine(s, label) {
        if (!s) return ""
        return label + ": " + P.number(s.requests) + " " + P.requests(s.requests)
               + ", " + s.sessions + " " + P.sessions(s.sessions)
    }

    function dayLabels() {
        var out = []
        var today = new Date(now * 1000)
        for (var i = 6; i >= 0; i--) {
            var day = new Date(today.getFullYear(), today.getMonth(), today.getDate() - i)
            var start = Math.max(day.getTime() / 1000, now - 7 * 86400)
            var end = Math.min(day.getTime() / 1000 + 86400, now)
            out.push({ name: P.dayShort(day), middle: ((start + end) / 2 - (now - 7 * 86400)) / (7 * 86400) })
        }
        return out
    }

    // bleed covers the padding Plasma leaves around a popup, so no rim of the system theme shows.
    Rectangle {
        anchors.fill: parent
        anchors.margins: -board.bleed
        color: board.tk.bg
        radius: board.tk.radius
    }

    Component { id: orbitBody; BodyOrbit { dash: board } }
    Component { id: linesBody; BodyRows { dash: board } }
    Component { id: terminalBody; BodyRows { dash: board; style: "text" } }
    Component { id: batteryBody; BodyRows { dash: board; style: "cells"; showLeft: true } }
    Component { id: paperBody; BodyPaper { dash: board } }

    ColumnLayout {
        id: column
        anchors.fill: parent
        anchors.margins: 16
        spacing: 14

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Canvas {
                Layout.preferredWidth: 20
                Layout.preferredHeight: 20
                onPaint: {
                    var c = getContext("2d")
                    c.reset()
                    c.strokeStyle = "#d97757"
                    c.lineWidth = 2.2
                    c.lineCap = "round"
                    for (var i = 0; i < 8; i++) {
                        var a = i * Math.PI / 4 + 0.2
                        var l = i % 2 ? 7 : 9
                        c.beginPath()
                        c.moveTo(10 + Math.cos(a) * 2, 10 + Math.sin(a) * 2)
                        c.lineTo(10 + Math.cos(a) * l, 10 + Math.sin(a) * l)
                        c.stroke()
                    }
                }
            }
            T {
                tk: board.tk
                text: "Claude Pulse"
                font.pixelSize: 16
                font.weight: Font.DemiBold
            }
            Rectangle {
                visible: !!(board.usage && board.usage.plan)
                Layout.preferredWidth: planLabel.implicitWidth + 14
                Layout.preferredHeight: 20
                radius: Math.min(10, board.tk.radius)
                color: board.tk.line
                T {
                    id: planLabel
                    anchors.centerIn: parent
                    tk: board.tk
                    text: board.usage && board.usage.plan ? board.usage.plan : ""
                    font.pixelSize: 11
                    font.weight: Font.DemiBold
                }
            }
            Item { Layout.fillWidth: true }
            T {
                visible: !!(board.usage && board.usage.fetched_at)
                tk: board.tk
                muted: true
                text: board.usage && board.usage.fetched_at ? P.ago(board.now - board.usage.fetched_at) : ""
                font.pixelSize: 12
            }
            Rectangle {
                Layout.preferredWidth: 28
                Layout.preferredHeight: 28
                radius: Math.min(14, board.tk.radius)
                color: refreshArea.containsMouse ? board.tk.line : "transparent"
                T {
                    id: refreshGlyph
                    anchors.centerIn: parent
                    tk: board.tk
                    text: "↻"
                    font.pixelSize: 17
                    RotationAnimator on rotation {
                        running: board.busy
                        loops: Animation.Infinite
                        from: 0; to: 360; duration: 900
                        onRunningChanged: if (!running) refreshGlyph.rotation = 0
                    }
                }
                MouseArea {
                    id: refreshArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: board.refreshRequested()
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: verdictColumn.implicitHeight + 20
            radius: board.tk.radius
            color: Qt.rgba(Qt.color(board.verdict.color).r, Qt.color(board.verdict.color).g, Qt.color(board.verdict.color).b, board.dark ? 0.16 : 0.13)
            Rectangle {
                id: verdictDot
                x: 12; y: 15
                width: 9; height: 9; radius: 4.5
                color: board.verdict.color
            }
            Column {
                id: verdictColumn
                anchors { left: verdictDot.right; leftMargin: 10; right: parent.right; rightMargin: 12; top: parent.top; topMargin: 10 }
                spacing: 1
                T {
                    width: parent.width
                    tk: board.tk
                    text: board.verdict.title
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                }
                T {
                    width: parent.width
                    tk: board.tk
                    text: board.verdict.text
                    font.pixelSize: 12
                    wrapMode: Text.WordWrap
                }
            }
        }

        Loader {
            Layout.fillWidth: true
            Layout.preferredHeight: item ? item.implicitHeight : 0
            sourceComponent: ({ orbit: orbitBody, lines: linesBody, terminal: terminalBody,
                                battery: batteryBody, paper: paperBody })[board.tk.name]
        }

        T {
            Layout.alignment: Qt.AlignHCenter
            tk: board.tk
            muted: true
            text: P.t("Tick: usage if spent evenly")
            font.pixelSize: 11
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: trendColumn.implicitHeight + 22
            radius: board.tk.radius
            color: board.tk.card
            ColumnLayout {
                id: trendColumn
                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 11 }
                spacing: 6
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    T {
                        tk: board.tk
                        text: P.t("Last 7 days")
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                    }
                    Item { Layout.fillWidth: true }
                    Rectangle { width: 10; height: 3; radius: 1.5; color: board.tk.session.b }
                    T { tk: board.tk; muted: true; text: P.t("session"); font.pixelSize: 11 }
                    Rectangle { width: 10; height: 3; radius: 1.5; color: board.tk.week.b; Layout.leftMargin: 6 }
                    T { tk: board.tk; muted: true; text: P.t("week"); font.pixelSize: 11 }
                }
                Item {
                    Layout.fillWidth: true
                    implicitHeight: 64
                    Trend {
                        anchors.fill: parent
                        history: board.usage && board.usage.history ? board.usage.history : []
                        now: board.now
                        gridColor: board.tk.line
                        sessionColor: board.tk.session.b
                        weekColor: board.tk.week.b
                    }
                    T {
                        anchors.centerIn: parent
                        visible: !board.usage || !board.usage.history || board.usage.history.length < 2
                        tk: board.tk
                        muted: true
                        text: P.t("The chart fills in after a few updates")
                        font.pixelSize: 12
                    }
                }
                Item {
                    id: dayRow
                    Layout.fillWidth: true
                    implicitHeight: 14
                    Repeater {
                        model: board.days
                        T {
                            required property var modelData
                            x: Math.max(0, Math.min(dayRow.width - width, dayRow.width * modelData.middle - width / 2))
                            tk: board.tk
                            muted: true
                            text: modelData.name
                            font.pixelSize: 11
                        }
                    }
                }
            }
        }

        T {
            Layout.fillWidth: true
            visible: text.length > 0
            tk: board.tk
            muted: true
            text: {
                if (!board.usage || !board.usage.stats) return ""
                var parts = [board.statLine(board.usage.stats.day, P.t("24 h")), board.statLine(board.usage.stats.week, P.t("7 days"))]
                return parts.filter(function (s) { return s.length > 0 }).join("\n")
            }
            font.pixelSize: 12
            lineHeight: 1.2
        }

        T {
            Layout.fillWidth: true
            visible: !!(board.usage && board.usage.ok === false && board.usage.fetched_at)
            tk: board.tk
            text: board.usage && board.usage.error
                  ? P.t("Could not update: %1", P.t(board.usage.error)) + ". " + P.t("Showing the last known data") : ""
            color: board.tk.danger
            font.pixelSize: 12
            wrapMode: Text.WordWrap
        }
    }
}
