import QtQuick
import QtQuick.Layouts
import "Palette.js" as P

// Large serif numbers, each over a thin bar.
ColumnLayout {
    id: body

    property var dash
    spacing: 14

    RowLayout {
        Layout.fillWidth: true
        spacing: 18

        Repeater {
            model: [
                { kind: "session", title: P.t("Session"), limit: body.dash.session },
                { kind: "week", title: P.t("Week"), limit: body.dash.week }
            ]
            ColumnLayout {
                required property var modelData
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                spacing: 3
                T {
                    tk: body.dash.tk
                    text: modelData.limit ? Math.round(modelData.limit.pct) + "%" : "—"
                    font.pixelSize: 50
                    lineHeight: 0.95
                }
                Bar {
                    Layout.fillWidth: true
                    visible: !!modelData.limit
                    tk: body.dash.tk
                    kind: modelData.kind
                    thickness: 3
                    pct: modelData.limit ? modelData.limit.pct : 0
                    pace: modelData.limit ? modelData.limit.pace : -1
                }
                T { Layout.topMargin: 4; tk: body.dash.tk; text: modelData.title; font.pixelSize: 15 }
                T {
                    tk: body.dash.tk
                    muted: true
                    font.pixelSize: 12
                    text: modelData.limit ? P.t("%1% left", Math.round(100 - modelData.limit.pct)) : body.dash.missingText(modelData.kind)
                }
                T {
                    visible: !!(modelData.limit && modelData.limit.reset)
                    tk: body.dash.tk
                    muted: true
                    font.pixelSize: 12
                    text: body.dash.resetText(modelData.limit)
                }
            }
        }
    }

    ModelRows {
        Layout.fillWidth: true
        dash: body.dash
    }
}
