import QtQuick
import QtQuick.Controls
import ".."

Button {
    id: root

    property bool primary: true
    property bool neonGlow: false
    property string iconSource: ""

    font.pixelSize: Theme.fontBody
    font.weight: Font.DemiBold
    horizontalPadding: Theme.spacingLg
    verticalPadding: Theme.spacingSm + 2

    contentItem: Row {
        spacing: Theme.spacingSm
        anchors.centerIn: parent

        Text {
            text: root.iconSource
            font.pixelSize: Theme.fontBody + 2
            color: root.primary ? (Theme.isDark ? "#0A0E1A" : "#FFFFFF") : Theme.textPrimary
            visible: root.iconSource !== ""
            anchors.verticalCenter: parent.verticalCenter
        }

        Text {
            text: root.text
            font: root.font
            color: root.primary ? (Theme.isDark ? "#0A0E1A" : "#FFFFFF") : Theme.textPrimary
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    background: Rectangle {
        id: bg
        radius: Theme.radiusSm
        color: {
            if (!root.enabled)
                return Theme.surfaceLight;
            if (root.pressed)
                return root.primary ? Qt.darker(Theme.accentNeon, 1.3) : Theme.surfaceLight;
            if (root.hovered)
                return root.primary ? Qt.lighter(Theme.accentNeon, 1.15) : Theme.navHover;
            if (root.activeFocus && !root.primary)
                return Theme.navHover;
            return root.primary ? Theme.accentNeon : Theme.surface;
        }
        border.color: {
            if (root.neonGlow && root.hovered) return Theme.accentNeon;
            if (root.activeFocus && root.enabled)
                return root.primary ? Qt.lighter(Theme.accentNeon, 1.35) : Theme.accentNeon;
            if (!root.primary) return Theme.glassBorderHover;
            return "transparent";
        }
        border.width: {
            if (root.activeFocus && root.enabled) return root.primary ? 3 : 2;
            if (!root.primary || root.neonGlow) return 1;
            return 0;
        }

        Behavior on color { ColorAnimation { duration: Theme.animFast } }
    }
}
