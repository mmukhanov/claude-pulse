import QtQuick
import QtQuick.Layouts
import "Palette.js" as P

// Stacked limits. Shared by Lines (bars), Terminal (text blocks) and Battery (cells left).
ColumnLayout {
    id: body

    property var dash
    property string style: "bar"
    property bool showLeft: false

    spacing: 12

    LimitRow {
        Layout.fillWidth: true
        dash: body.dash
        title: P.t("Session")
        kind: "session"
        style: body.style
        showLeft: body.showLeft
        limit: body.dash.session
    }
    LimitRow {
        Layout.fillWidth: true
        dash: body.dash
        title: P.t("Week")
        kind: "week"
        style: body.style
        showLeft: body.showLeft
        limit: body.dash.week
    }
    ModelRows {
        Layout.fillWidth: true
        dash: body.dash
        style: body.style
        showLeft: body.showLeft
    }
}
