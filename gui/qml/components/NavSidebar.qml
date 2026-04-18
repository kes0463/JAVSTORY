import QtQuick
import QtQuick.Controls
import ".."

Rectangle {
    id: root

    property int currentIndex: 0
    property bool collapsed: false
    /** 폴더 연결 알림 대기 건수 (사이드바 배지) */
    property int folderAlertCount: 0
    signal navigate(int index)
    signal openFolderAlerts()

    width: collapsed ? 72 : 260
    Behavior on width { NumberAnimation { duration: Theme.animNormal; easing.type: Easing.OutCubic } }

    color: Theme.navBg
    border.color: Theme.glassBorder
    border.width: 0

    // 우측 경계선
    Rectangle {
        anchors.right: parent.right
        width: 1; height: parent.height
        color: Theme.glassBorder
    }

    // ── 상단: 로고 + 네비게이션 ────────────────────
    Column {
        id: topNav
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        spacing: 0

        Item {
            width: parent.width
            height: 72

            Row {
                anchors.centerIn: parent
                spacing: Theme.spacingSm

                Text {
                    text: "\u2B50"
                    font.pixelSize: 22
                    anchors.verticalCenter: parent.verticalCenter
                }

                Text {
                    visible: !root.collapsed
                    text: "JAVSTORY"
                    font.pixelSize: Theme.fontSubtitle
                    font.weight: Font.ExtraBold
                    font.letterSpacing: 1.5
                    color: Theme.mode === 0 ? Theme.textPrimary : Theme.accentNeon
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: root.collapsed = !root.collapsed
            }
        }

        Rectangle { width: parent.width; height: 1; color: Theme.glassBorder }

        Repeater {
            model: ListModel {
                ListElement { label: "대시보드";     icon: "\uD83C\uDFE0" }
                ListElement { label: "수집";        icon: "\uD83D\uDD0D" }
                ListElement { label: "전사·자막";   icon: "\uD83C\uDFA4" }
                ListElement { label: "라이브러리";   icon: "\uD83D\uDCDA" }
            }

            delegate: Rectangle {
                width: root.width
                height: 48
                color: root.currentIndex === index ? Theme.navActive
                     : navMouse.containsMouse     ? Theme.navHover
                     : "transparent"

                Behavior on color { ColorAnimation { duration: Theme.animFast } }

                Rectangle {
                    visible: root.currentIndex === index
                    anchors.left: parent.left
                    width: 3; height: 24
                    anchors.verticalCenter: parent.verticalCenter
                    radius: 2
                    color: Theme.accentNeon
                }

                Row {
                    anchors.left: parent.left
                    anchors.leftMargin: Theme.spacingMd
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: Theme.spacingSm + 4

                    Text {
                        text: model.icon
                        font.pixelSize: 18
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    Text {
                        visible: !root.collapsed
                        text: model.label
                        font.pixelSize: Theme.fontBody
                        font.weight: root.currentIndex === index ? Font.DemiBold : Font.Normal
                        color: root.currentIndex === index ? Theme.textPrimary : Theme.textSecondary
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                MouseArea {
                    id: navMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        root.currentIndex = index;
                        root.navigate(index);
                    }
                }
            }
        }
    }

    // ── 하단: 알림 + 설정 ────────────────────────────
    Column {
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        spacing: 0

        Rectangle { width: parent.width; height: 1; color: Theme.glassBorder }

        // 폴더 연결 알림 인박스
        Rectangle {
            width: root.width
            height: 48
            color: folderBellMouse.containsMouse ? Theme.navHover : "transparent"
            Behavior on color { ColorAnimation { duration: Theme.animFast } }

            Row {
                anchors.left: parent.left
                anchors.leftMargin: Theme.spacingMd
                anchors.verticalCenter: parent.verticalCenter
                spacing: Theme.spacingSm + 4

                Item {
                    width: 28
                    height: 28
                    anchors.verticalCenter: parent.verticalCenter

                    Text {
                        anchors.centerIn: parent
                        text: "\uD83D\uDD14"
                        font.pixelSize: 18
                    }

                    Rectangle {
                        visible: root.folderAlertCount > 0
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.rightMargin: -4
                        anchors.topMargin: -4
                        width: Math.max(18, badgeLabel.implicitWidth + 6)
                        height: 18
                        radius: 9
                        color: Theme.error

                        Label {
                            id: badgeLabel
                            anchors.centerIn: parent
                            text: root.folderAlertCount > 99 ? "99+" : root.folderAlertCount
                            color: "#FFFFFF"
                            font.pixelSize: 11
                            font.bold: true
                        }
                    }
                }

                Text {
                    visible: !root.collapsed
                    text: "폴더 알림"
                    font.pixelSize: Theme.fontBody
                    font.weight: Font.Normal
                    color: Theme.textSecondary
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            MouseArea {
                id: folderBellMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.openFolderAlerts()
            }
        }

        Rectangle {
            width: root.width
            height: 48
            color: root.currentIndex === 4 ? Theme.navActive
                 : settingsMouse.containsMouse ? Theme.navHover
                 : "transparent"

            Behavior on color { ColorAnimation { duration: Theme.animFast } }

            Rectangle {
                visible: root.currentIndex === 4
                anchors.left: parent.left
                width: 3; height: 24
                anchors.verticalCenter: parent.verticalCenter
                radius: 2
                color: Theme.accentNeon
            }

            Row {
                anchors.left: parent.left
                anchors.leftMargin: Theme.spacingMd
                anchors.verticalCenter: parent.verticalCenter
                spacing: Theme.spacingSm + 4

                Text {
                    text: "\u2699\uFE0F"
                    font.pixelSize: 18
                    anchors.verticalCenter: parent.verticalCenter
                }

                Text {
                    visible: !root.collapsed
                    text: "설정"
                    font.pixelSize: Theme.fontBody
                    font.weight: root.currentIndex === 4 ? Font.DemiBold : Font.Normal
                    color: root.currentIndex === 4 ? Theme.textPrimary : Theme.textSecondary
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            MouseArea {
                id: settingsMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    root.currentIndex = 4;
                    root.navigate(4);
                }
            }
        }
    }
}
