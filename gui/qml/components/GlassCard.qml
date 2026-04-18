import QtQuick
import QtQuick.Controls
import ".."

Rectangle {
    id: root

    property alias contentItem: contentLoader.item
    default property alias content: contentArea.data

    property bool hoverGlow: false

    color: Theme.surface
    border.color: hoverArea.containsMouse && hoverGlow
                  ? Theme.glassBorderHover : Theme.glassBorder
    border.width: 1
    radius: Theme.radiusMd

    Behavior on border.color { ColorAnimation { duration: Theme.animFast } }

    implicitHeight: contentArea.childrenRect.height + Theme.spacingMd * 2
    implicitWidth: 300

    MouseArea {
        id: hoverArea
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.NoButton
        propagateComposedEvents: true
    }

    Loader { id: contentLoader; active: false }

    Item {
        id: contentArea
        anchors {
            fill: parent
            margins: Theme.spacingMd
        }
    }
}
