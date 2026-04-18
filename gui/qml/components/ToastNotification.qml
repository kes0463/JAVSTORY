import QtQuick
import ".."

Rectangle {
    id: root

    property string message: ""
    property string level: "info"  // info, success, warning, error
    property int duration: 3000

    signal dismissed()

    width: toastText.implicitWidth + Theme.spacingLg * 2
    height: 40
    radius: Theme.radiusSm
    opacity: 0
    visible: opacity > 0

    color: {
        switch (level) {
        case "success": return Qt.rgba(52/255, 211/255, 153/255, 0.90);
        case "warning": return Qt.rgba(251/255, 191/255, 36/255, 0.90);
        case "error":   return Qt.rgba(248/255, 113/255, 113/255, 0.90);
        default:        return Qt.rgba(0, 136/255, 1, 0.90);
        }
    }

    Text {
        id: toastText
        anchors.centerIn: parent
        text: root.message
        font.pixelSize: Theme.fontBody
        font.weight: Font.Medium
        color: (root.level === "warning" || root.level === "success") ? "#0A0E1A" : "#FFFFFF"
    }

    function show(msg, lvl) {
        root.message = msg;
        root.level = lvl || "info";
        showAnim.start();
        hideTimer.restart();
    }

    Timer {
        id: hideTimer
        interval: root.duration
        onTriggered: hideAnim.start()
    }

    NumberAnimation {
        id: showAnim
        target: root; property: "opacity"
        from: 0; to: 1; duration: Theme.animFast
    }

    NumberAnimation {
        id: hideAnim
        target: root; property: "opacity"
        from: 1; to: 0; duration: Theme.animNormal
        onFinished: root.dismissed()
    }
}
