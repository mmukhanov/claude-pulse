import QtQuick
import org.kde.plasma.configuration
import "../ui/Palette.js" as P

ConfigModel {
    ConfigCategory {
        name: P.t("General")
        icon: "preferences-desktop-plasma"
        source: "configGeneral.qml"
    }
}
