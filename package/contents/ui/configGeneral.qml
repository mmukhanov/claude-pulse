import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kcmutils as KCM
import org.kde.kirigami as Kirigami
import "Palette.js" as P

KCM.SimpleKCM {
    property alias cfg_showNumbers: showNumbers.checked

    Kirigami.FormLayout {
        QQC2.CheckBox {
            id: showNumbers
            Kirigami.FormData.label: P.t("Panel icon:")
            text: P.t("Show numbers next to the rings")
        }
    }
}
