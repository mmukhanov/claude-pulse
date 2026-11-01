import QtQuick
import QtQuick.Layouts
import "Palette.js" as P

// Weekly limits for individual models, in the style of the current theme.
ColumnLayout {
    id: models

    property var dash
    property string style: "bar"
    property bool showLeft: false

    spacing: 10
    visible: repeater.count > 0

    Repeater {
        id: repeater
        model: models.dash.usage && models.dash.usage.models ? models.dash.usage.models : []
        LimitRow {
            required property var modelData
            Layout.fillWidth: true
            dash: models.dash
            kind: "week"
            style: models.style
            showLeft: models.showLeft
            title: P.t("Week, %1", modelData.name)
            limit: modelData
        }
    }
}
