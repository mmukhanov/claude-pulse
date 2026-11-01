import QtQuick
import QtQuick.Layouts
import "Palette.js" as P

// One limit window: ring with the percentage inside, remaining and reset below.
ColumnLayout {
    id: gauge

    property string title
    property string subtitle
    property string kind: "session"
    property var limit: null
    property real now
    property color textColor
    property color mutedColor
    property color trackColor
    property color paceColor

    readonly property real pct: limit ? limit.pct : 0
    readonly property var colors: P.level(pct, kind)

    spacing: 2

    Item {
        Layout.alignment: Qt.AlignHCenter
        Layout.preferredWidth: 156
        Layout.preferredHeight: 156

        Ring {
            anchors.fill: parent
            value: gauge.pct
            pace: gauge.limit ? gauge.limit.pace : -1
            thickness: 13
            glow: 7
            colorA: gauge.colors.a
            colorB: gauge.colors.b
            trackColor: gauge.trackColor
            paceColor: gauge.paceColor
        }
        Column {
            anchors.centerIn: parent
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: gauge.limit ? Math.round(gauge.pct) + "%" : "—"
                color: gauge.textColor
                font.pixelSize: 38
                font.weight: Font.Bold
                font.letterSpacing: -1
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                visible: !!gauge.limit
                text: P.t("used")
                color: gauge.mutedColor
                font.pixelSize: 11
            }
        }
    }

    Row {
        Layout.alignment: Qt.AlignHCenter
        Layout.topMargin: 6
        spacing: 6
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: 9; height: 9; radius: 4.5
            color: P.level(0, gauge.kind).b
        }
        Text {
            text: gauge.title
            color: gauge.textColor
            font.pixelSize: 15
            font.weight: Font.DemiBold
        }
    }
    Text {
        Layout.alignment: Qt.AlignHCenter
        text: gauge.limit ? P.t("%1% left", Math.round(100 - gauge.pct)) : gauge.subtitle
        color: gauge.textColor
        font.pixelSize: 13
    }
    Text {
        Layout.alignment: Qt.AlignHCenter
        visible: !!(gauge.limit && gauge.limit.reset)
        text: gauge.limit && gauge.limit.reset
              ? P.t("resets in %1", P.duration(gauge.limit.reset - gauge.now)) : ""
        color: gauge.mutedColor
        font.pixelSize: 12
    }
    Text {
        Layout.alignment: Qt.AlignHCenter
        visible: !!(gauge.limit && gauge.limit.reset)
        text: gauge.limit && gauge.limit.reset ? P.clock(gauge.limit.reset, gauge.now) : ""
        color: gauge.mutedColor
        font.pixelSize: 12
    }
}
