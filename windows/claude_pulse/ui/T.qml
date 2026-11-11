import QtQuick

// Text in the current theme's font. Always plain, since some strings come from the CLI.
Text {
    property var tk
    property bool muted: false

    color: tk ? (muted ? tk.muted : tk.text) : "#888888"
    font.family: tk && tk.font ? tk.font : Qt.application.font.family
    font.pixelSize: 13
    textFormat: Text.PlainText
}
