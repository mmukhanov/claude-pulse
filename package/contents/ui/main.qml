import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as P5
import org.kde.kirigami as Kirigami
import "Palette.js" as P

PlasmoidItem {
    id: root

    property var usage: null
    property bool busy: false
    property real now: Date.now() / 1000

    readonly property int refreshSeconds: usage && usage.settings ? usage.settings.interval_minutes * 60 : 300
    readonly property string script: decodeURIComponent(Qt.resolvedUrl("../code/fetch.py").toString().replace("file://", ""))
    readonly property var session: usage ? usage.session : null
    readonly property var week: usage ? usage.week : null

    function refresh(force) {
        if (busy) return
        busy = true
        exec.connectSource("python3 -I '" + script.replace(/'/g, "'\\''") + "'" + (force ? " --force" : ""))
    }

    function tipLine(name, w) {
        if (!w) return week ? P.t("%1: no limit", name) : ""
        var line = P.t("%1: %2% used, %3% left", name, Math.round(w.pct), Math.round(100 - w.pct))
        if (w.reset) line += ", " + P.t("resets in %1", P.duration(w.reset - now))
        if (w.runout) line += ", " + P.t("may hit the limit")
        return line
    }

    P5.DataSource {
        id: exec
        engine: "executable"
        onNewData: (source, data) => {
            disconnectSource(source)
            root.busy = false
            try {
                const parsed = JSON.parse(data["stdout"])
                if (parsed.settings)
                    P.setLanguage(parsed.settings.language)
                if (parsed.fetched_at || !root.usage)
                    root.usage = parsed
                root.now = Date.now() / 1000
            } catch (e) {
                root.usage = Object.assign({}, root.usage || {}, { ok: false, error: P.t("The data collector did not answer") })
            }
        }
    }

    Timer {
        interval: root.refreshSeconds * 1000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: root.refresh(true)
    }
    Timer {
        interval: 30000
        running: true
        repeat: true
        onTriggered: root.now = Date.now() / 1000
    }

    onExpandedChanged: (isExpanded) => {
        if (isExpanded) {
            now = Date.now() / 1000
            refresh(false)
        }
    }

    Plasmoid.icon: "utilities-system-monitor"
    Plasmoid.status: (session && (session.pct >= 85 || session.runout)) || (week && (week.pct >= 85 || week.runout))
                     ? PlasmaCore.Types.ActiveStatus : PlasmaCore.Types.PassiveStatus
    toolTipMainText: "Claude Pulse"
    toolTipSubText: {
        if (!usage || (!session && !week)) return P.t("No data")
        return [usage.plan ? P.t("Plan: %1", usage.plan) : "", tipLine(P.t("Session"), session), tipLine(P.t("Week"), week)].filter(s => s.length > 0).join("\n")
    }

    compactRepresentation: MouseArea {
        Layout.minimumWidth: icon.implicitWidth
        Layout.preferredWidth: icon.implicitWidth
        Layout.minimumHeight: 16
        hoverEnabled: true
        onClicked: root.expanded = !root.expanded

        PanelIcon {
            id: icon
            anchors.fill: parent
            usage: root.usage
            showNumbers: Plasmoid.configuration.showNumbers
            textColor: Kirigami.Theme.textColor
            mutedColor: Kirigami.Theme.disabledTextColor
            trackColor: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.2)
        }
    }

    fullRepresentation: Item {
        Layout.minimumWidth: dashboard.implicitWidth
        Layout.preferredWidth: dashboard.implicitWidth
        Layout.minimumHeight: dashboard.implicitHeight
        Layout.preferredHeight: dashboard.implicitHeight

        Dashboard {
            id: dashboard
            anchors.fill: parent
            usage: root.usage
            busy: root.busy
            now: root.now
            textColor: Kirigami.Theme.textColor
            mutedColor: Kirigami.Theme.disabledTextColor
            backgroundColor: Kirigami.Theme.backgroundColor
            onRefreshRequested: root.refresh(true)
        }
    }
}
