import QtQuick
import QtQuick.Layouts
import "Palette.js" as P

// The popup. Plain QtQuick with colours passed in, so it follows the Plasma
// theme and can also be rendered outside the shell.
Item {
    id: dash

    property var usage: null
    property bool busy: false
    property real now: Date.now() / 1000
    property color textColor: "#eeeeee"
    property color mutedColor: "#aaaaaa"
    property color backgroundColor: "#202028"
    signal refreshRequested()

    readonly property bool dark: (backgroundColor.r + backgroundColor.g + backgroundColor.b) / 3 < 0.5
    readonly property color cardColor: dark ? Qt.rgba(1, 1, 1, 0.055) : Qt.rgba(0, 0, 0, 0.04)
    readonly property color trackColor: dark ? Qt.rgba(1, 1, 1, 0.12) : Qt.rgba(0, 0, 0, 0.10)
    readonly property color gridColor: dark ? Qt.rgba(1, 1, 1, 0.09) : Qt.rgba(0, 0, 0, 0.09)
    readonly property color sessionLine: dark ? "#22d3ee" : "#0891b2"
    readonly property color weekLine: dark ? "#a78bfa" : "#7c3aed"
    readonly property var session: usage ? usage.session : null
    readonly property var week: usage ? usage.week : null
    readonly property var verdict: makeVerdict()

    implicitWidth: 420
    implicitHeight: column.implicitHeight + 32

    function makeVerdict() {
        if (!usage || (!session && !week))
            return { color: "#94a3b8", title: P.t("No data"), text: usage && usage.error ? P.t(usage.error) : P.t("Waiting for the first answer from Claude Code") }
        var hard = (session && session.pct >= 100) ? session : (week && week.pct >= 100 ? week : null)
        if (hard) {
            var what = P.t(hard === session ? "Session limit reached" : "Week limit reached")
            return { color: "#ef4444", title: P.t("Limit reached"),
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

    ColumnLayout {
        id: column
        anchors.fill: parent
        anchors.margins: 16
        spacing: 14

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Canvas {
                width: 20; height: 20
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
            Text {
                text: "Claude Pulse"
                color: dash.textColor
                font.pixelSize: 16
                font.weight: Font.DemiBold
            }
            Rectangle {
                visible: !!(dash.usage && dash.usage.plan)
                Layout.preferredWidth: planLabel.implicitWidth + 14
                Layout.preferredHeight: 20
                radius: 10
                color: dash.trackColor
                Text {
                    id: planLabel
                    anchors.centerIn: parent
                    text: dash.usage && dash.usage.plan ? dash.usage.plan : ""
                    textFormat: Text.PlainText
                    color: dash.textColor
                    font.pixelSize: 11
                    font.weight: Font.DemiBold
                }
            }
            Item { Layout.fillWidth: true }
            Text {
                visible: !!(dash.usage && dash.usage.fetched_at)
                text: dash.usage && dash.usage.fetched_at ? P.ago(dash.now - dash.usage.fetched_at) : ""
                color: dash.mutedColor
                font.pixelSize: 12
            }
            Rectangle {
                id: refreshButton
                width: 28; height: 28; radius: 14
                Layout.preferredWidth: 28
                Layout.preferredHeight: 28
                color: refreshArea.containsMouse ? dash.trackColor : "transparent"
                Text {
                    id: refreshGlyph
                    anchors.centerIn: parent
                    text: "↻"
                    color: dash.textColor
                    font.pixelSize: 17
                    RotationAnimator on rotation {
                        running: dash.busy
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
                    onClicked: dash.refreshRequested()
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: verdictColumn.implicitHeight + 20
            radius: 12
            color: Qt.rgba(Qt.color(dash.verdict.color).r, Qt.color(dash.verdict.color).g, Qt.color(dash.verdict.color).b, dash.dark ? 0.16 : 0.13)
            Rectangle {
                id: verdictDot
                x: 12; y: 15
                width: 9; height: 9; radius: 4.5
                color: dash.verdict.color
            }
            Column {
                id: verdictColumn
                anchors { left: verdictDot.right; leftMargin: 10; right: parent.right; rightMargin: 12; top: parent.top; topMargin: 10 }
                spacing: 1
                Text {
                    width: parent.width
                    text: dash.verdict.title
                    color: dash.textColor
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                }
                Text {
                    width: parent.width
                    text: dash.verdict.text
                    textFormat: Text.PlainText
                    color: dash.textColor
                    opacity: 0.8
                    font.pixelSize: 12
                    wrapMode: Text.WordWrap
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 0
            Item { Layout.fillWidth: true }
            Gauge {
                title: P.t("Session")
                subtitle: dash.week ? P.t("No 5-hour limit") : P.t("5-hour window")
                limit: dash.session
                now: dash.now
                textColor: dash.textColor
                mutedColor: dash.mutedColor
                trackColor: dash.trackColor
                paceColor: dash.textColor
            }
            Item { Layout.fillWidth: true }
            Gauge {
                title: P.t("Week")
                kind: "week"
                subtitle: P.t("7-day window")
                limit: dash.week
                now: dash.now
                textColor: dash.textColor
                mutedColor: dash.mutedColor
                trackColor: dash.trackColor
                paceColor: dash.textColor
            }
            Item { Layout.fillWidth: true }
        }

        Text {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: -6
            text: P.t("Tick on the ring: usage if spent evenly")
            color: dash.mutedColor
            font.pixelSize: 11
        }

        Repeater {
            model: dash.usage && dash.usage.models ? dash.usage.models : []
            delegate: ColumnLayout {
                id: modelRow
                required property var modelData
                Layout.fillWidth: true
                spacing: 5
                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        text: P.t("Week, %1", modelRow.modelData.name)
                        textFormat: Text.PlainText
                        color: dash.textColor
                        font.pixelSize: 13
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: P.t("%1%, %2% left", Math.round(modelRow.modelData.pct), Math.round(100 - modelRow.modelData.pct))
                        color: dash.mutedColor
                        font.pixelSize: 12
                    }
                }
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 7
                    radius: 3.5
                    color: dash.trackColor
                    Rectangle {
                        height: parent.height
                        radius: parent.radius
                        width: Math.max(height, parent.width * Math.min(100, modelRow.modelData.pct) / 100)
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0; color: P.level(modelRow.modelData.pct, "week").a }
                            GradientStop { position: 1; color: P.level(modelRow.modelData.pct, "week").b }
                        }
                        Behavior on width { NumberAnimation { duration: 900; easing.type: Easing.OutCubic } }
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: trendColumn.implicitHeight + 22
            radius: 12
            color: dash.cardColor
            ColumnLayout {
                id: trendColumn
                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 11 }
                spacing: 8
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    Text {
                        text: P.t("Last 24 hours")
                        color: dash.textColor
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                    }
                    Item { Layout.fillWidth: true }
                    Rectangle { width: 10; height: 3; radius: 1.5; color: dash.sessionLine }
                    Text { text: P.t("session"); color: dash.mutedColor; font.pixelSize: 11 }
                    Rectangle { width: 10; height: 3; radius: 1.5; color: dash.weekLine; Layout.leftMargin: 6 }
                    Text { text: P.t("week"); color: dash.mutedColor; font.pixelSize: 11 }
                }
                Item {
                    Layout.fillWidth: true
                    implicitHeight: 64
                    Trend {
                        anchors.fill: parent
                        history: dash.usage && dash.usage.history ? dash.usage.history : []
                        now: dash.now
                        gridColor: dash.gridColor
                        sessionColor: dash.sessionLine
                        weekColor: dash.weekLine
                    }
                    Text {
                        anchors.centerIn: parent
                        visible: !dash.usage || !dash.usage.history || dash.usage.history.length < 2
                        text: P.t("The chart fills in after a few updates")
                        color: dash.mutedColor
                        font.pixelSize: 12
                    }
                }
            }
        }

        Text {
            Layout.fillWidth: true
            visible: text.length > 0
            text: {
                if (!dash.usage || !dash.usage.stats) return ""
                var parts = [dash.statLine(dash.usage.stats.day, P.t("24 h")), dash.statLine(dash.usage.stats.week, P.t("7 days"))]
                return parts.filter(function (s) { return s.length > 0 }).join("\n")
            }
            color: dash.mutedColor
            font.pixelSize: 12
            lineHeight: 1.2
        }

        Text {
            Layout.fillWidth: true
            visible: !!(dash.usage && dash.usage.ok === false && dash.usage.fetched_at)
            text: dash.usage && dash.usage.error
                  ? P.t("Could not update: %1", P.t(dash.usage.error)) + ". " + P.t("Showing the last known data") : ""
            textFormat: Text.PlainText
            color: "#ef4444"
            font.pixelSize: 12
            wrapMode: Text.WordWrap
        }
    }
}
