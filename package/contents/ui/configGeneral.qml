import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kcmutils as KCM
import org.kde.kirigami as Kirigami
import "Palette.js" as P

KCM.SimpleKCM {
    property alias cfg_showNumbers: showNumbers.checked
    property string cfg_theme
    property string cfg_colorMode

    Kirigami.FormLayout {
        QQC2.ComboBox {
            Kirigami.FormData.label: P.t("Theme:")
            textRole: "label"
            valueRole: "value"
            model: [
                { value: "orbit", label: P.t("Orbit") },
                { value: "lines", label: P.t("Lines") },
                { value: "terminal", label: P.t("Terminal") },
                { value: "battery", label: P.t("Battery") },
                { value: "paper", label: P.t("Paper") }
            ]
            currentIndex: Math.max(0, indexOfValue(cfg_theme))
            onActivated: cfg_theme = currentValue
        }
        QQC2.ComboBox {
            Kirigami.FormData.label: P.t("Appearance:")
            textRole: "label"
            valueRole: "value"
            model: [
                { value: "system", label: P.t("Follow the system") },
                { value: "light", label: P.t("Light") },
                { value: "dark", label: P.t("Dark") }
            ]
            currentIndex: Math.max(0, indexOfValue(cfg_colorMode))
            onActivated: cfg_colorMode = currentValue
        }
        QQC2.CheckBox {
            id: showNumbers
            Kirigami.FormData.label: P.t("Panel icon:")
            text: P.t("Show numbers next to the icon")
        }
    }
}
