import QtQuick
import QtQuick.Layouts
import "Palette.js" as P
import "Themes.js" as Th

// One large double ring with the details beside it.
ColumnLayout {
    id: body

    property var dash
    readonly property var tk: dash.tk
    readonly property var session: dash.session
    readonly property var week: dash.week

    spacing: 14

    RowLayout {
        Layout.fillWidth: true
        spacing: 18

        Item {
            Layout.preferredWidth: 176
            Layout.preferredHeight: 176

            Ring {
                anchors.fill: parent
                visible: !!body.session || !body.week
                value: body.session ? body.session.pct : 0
                pace: body.session ? body.session.pace : -1
                thickness: 15
                glow: 6
                colorA: Th.limitColors(body.tk, "session", value).a
                colorB: Th.limitColors(body.tk, "session", value).b
                trackColor: body.tk.line
                paceColor: body.tk.text
            }
            Ring {
                anchors.centerIn: parent
                width: 126
                height: 126
                value: body.week ? body.week.pct : 0
                pace: body.week ? body.week.pace : -1
                thickness: 15
                glow: 6
                colorA: Th.limitColors(body.tk, "week", value).a
                colorB: Th.limitColors(body.tk, "week", value).b
                trackColor: body.tk.line
                paceColor: body.tk.text
            }
            Column {
                anchors.centerIn: parent
                T {
                    anchors.horizontalCenter: parent.horizontalCenter
                    tk: body.tk
                    text: body.week ? Math.round(100 - body.week.pct) + "%" : "—"
                    font.pixelSize: 21
                    font.weight: Font.Bold
                }
                T {
                    anchors.horizontalCenter: parent.horizontalCenter
                    visible: !!body.week
                    tk: body.tk
                    muted: true
                    text: P.t("left this week")
                    font.pixelSize: 9
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2

            Repeater {
                model: [
                    { kind: "session", title: P.t("Session"), limit: body.session },
                    { kind: "week", title: P.t("Week"), limit: body.week }
                ]
                ColumnLayout {
                    required property var modelData
                    required property int index
                    Layout.topMargin: index > 0 ? 12 : 0
                    spacing: 1
                    RowLayout {
                        spacing: 6
                        Rectangle {
                            width: 9; height: 9; radius: 4.5
                            color: Th.limitColors(body.tk, modelData.kind, modelData.limit ? modelData.limit.pct : 0).b
                        }
                        T { tk: body.tk; text: modelData.title; font.pixelSize: 15; font.weight: Font.DemiBold }
                    }
                    T {
                        tk: body.tk
                        font.pixelSize: 13
                        text: modelData.limit ? P.t("%1% used", Math.round(modelData.limit.pct)) : body.dash.missingText(modelData.kind)
                    }
                    T {
                        visible: !!modelData.limit
                        tk: body.tk
                        font.pixelSize: 13
                        text: modelData.limit ? P.t("%1% left", Math.round(100 - modelData.limit.pct)) : ""
                    }
                    T {
                        visible: !!(modelData.limit && modelData.limit.reset)
                        tk: body.tk
                        muted: true
                        font.pixelSize: 12
                        text: body.dash.resetText(modelData.limit)
                    }
                }
            }
        }
    }

    ModelRows {
        Layout.fillWidth: true
        dash: body.dash
    }
}
