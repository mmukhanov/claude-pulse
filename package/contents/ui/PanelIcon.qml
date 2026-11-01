import QtQuick
import "Palette.js" as P

// Panel icon: outer ring is the session, inner ring is the week.
Item {
    id: icon

    property var usage: null
    property color textColor: "#eeeeee"
    property color mutedColor: "#aaaaaa"
    property color trackColor: "#40808080"
    property bool showNumbers: true

    readonly property var session: usage ? usage.session : null
    readonly property var week: usage ? usage.week : null
    readonly property real sessionPct: session ? session.pct : 0
    readonly property real weekPct: week ? week.pct : 0
    readonly property bool critical: sessionPct >= 90 || weekPct >= 90
    readonly property int ringSize: Math.max(16, Math.min(height, 32))

    implicitWidth: rings.width + (showNumbers ? 5 + label.implicitWidth + 2 : 0)
    implicitHeight: 24

    Item {
        id: rings
        width: icon.ringSize
        height: icon.ringSize
        anchors.verticalCenter: parent.verticalCenter

        Ring {
            anchors.fill: parent
            // No session limit on this plan: the week ring is all there is.
            visible: !!icon.session || !icon.week
            value: icon.sessionPct
            thickness: Math.max(2.5, icon.ringSize * 0.13)
            colorA: P.level(icon.sessionPct, "session").a
            colorB: P.level(icon.sessionPct, "session").b
            trackColor: icon.trackColor
        }
        Ring {
            anchors.centerIn: parent
            width: parent.width * 0.60
            height: parent.height * 0.60
            value: icon.weekPct
            thickness: Math.max(2.5, icon.ringSize * 0.13)
            colorA: P.level(icon.weekPct, "week").a
            colorB: P.level(icon.weekPct, "week").b
            trackColor: icon.trackColor
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
        width: Math.max(6, icon.ringSize * 0.3)
        height: width
        radius: width / 2
        color: "#f97316"
        border.color: icon.textColor
        border.width: 1
        anchors.right: rings.right
        anchors.top: rings.top
    }

    Row {
        id: label
        visible: icon.showNumbers
        anchors.left: rings.right
        anchors.leftMargin: 5
        anchors.verticalCenter: parent.verticalCenter
        spacing: 4
        Text {
            visible: !!icon.session || !icon.week
            text: icon.session ? Math.round(icon.sessionPct) + "%" : "—"
            color: icon.textColor
            font.pixelSize: Math.min(13, Math.max(10, icon.height * 0.48))
            font.weight: Font.DemiBold
        }
        Text {
            visible: !!icon.week
            text: Math.round(icon.weekPct) + "%"
            color: icon.mutedColor
            font.pixelSize: Math.min(13, Math.max(10, icon.height * 0.48))
        }
    }
}
