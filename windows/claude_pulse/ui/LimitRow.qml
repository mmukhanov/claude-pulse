import QtQuick
import QtQuick.Layouts
import "Palette.js" as P

// A named limit: title and percentage, bar, then what's left and the reset time.
ColumnLayout {
    id: row

    property var dash
    property string title
    property string kind: "session"
    property string style: "bar"
    property var limit: null
    property bool showLeft: false

    readonly property real pct: limit ? limit.pct : 0
    spacing: 4

    RowLayout {
        Layout.fillWidth: true
        T { tk: row.dash.tk; text: row.title }
        Item { Layout.fillWidth: true }
        T {
            tk: row.dash.tk
            visible: !!row.limit
            text: row.showLeft ? Math.round(100 - row.pct) + "%" : Math.round(row.pct) + "%"
            font.weight: Font.DemiBold
            font.pixelSize: row.showLeft ? 20 : 13
        }
    }
    Bar {
        Layout.fillWidth: true
        visible: !!row.limit
        tk: row.dash.tk
        kind: row.kind
        style: row.style
        pct: row.pct
        pace: row.limit && row.limit.pace !== undefined ? row.limit.pace : -1
    }
    RowLayout {
        Layout.fillWidth: true
        T {
            tk: row.dash.tk
            muted: true
            font.pixelSize: 12
            text: row.limit ? (row.showLeft ? P.t("left, used %1%", Math.round(row.pct)) : P.t("%1% left", Math.round(100 - row.pct)))
                            : row.dash.missingText(row.kind)
        }
        Item { Layout.fillWidth: true }
        T {
            tk: row.dash.tk
            muted: true
            font.pixelSize: 12
            visible: !!(row.limit && row.limit.reset)
            text: row.dash.resetText(row.limit)
        }
    }
}
