import QtQuick
import QtQuick.Controls
import ".."

Rectangle {
    id: root

    property string productCode: ""
    property string titleKo: ""
    property string actorsKo: ""
    property int sceneCount: 0
    property string coverPath: ""
    property string pipelineStage: "none"
    property bool hasCanonical: false
    property int partCount: 1
    property bool hasJaSrt: false
    property bool hasKoSrt: false
    property bool lampHardcoded: false

    signal clicked(string sku)

    width: 200
    height: 300
    radius: Theme.radiusMd
    color: Theme.surface
    border.color: mouseArea.containsMouse ? Theme.glassBorderHover : Theme.glassBorder
    border.width: 1
    clip: true

    scale: mouseArea.containsMouse ? 1.03 : 1.0
    Behavior on scale { NumberAnimation { duration: Theme.animFast; easing.type: Easing.OutCubic } }
    Behavior on border.color { ColorAnimation { duration: Theme.animFast } }

    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked(root.productCode)
    }

    Column {
        anchors.fill: parent
        spacing: 0

        // 커버 이미지
        Rectangle {
            width: parent.width
            height: 200
            color: Theme.bgSecondary
            clip: true

            Image {
                anchors.fill: parent
                source: root.coverPath ? "file:///" + root.coverPath : ""
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                visible: status === Image.Ready
            }

            Text {
                anchors.centerIn: parent
                text: root.productCode
                font.pixelSize: Theme.fontSubtitle
                font.weight: Font.Bold
                color: Theme.textMuted
                visible: !root.coverPath
            }
        }

        // 정보 영역
        Column {
            width: parent.width
            padding: Theme.spacingSm
            spacing: 4

            Text {
                text: root.productCode
                font.pixelSize: Theme.fontCaption
                font.weight: Font.Bold
                color: Theme.accentNeon
                width: parent.width - Theme.spacingSm * 2
            }

            Text {
                text: root.titleKo || "제목 없음"
                font.pixelSize: Theme.fontCaption
                color: Theme.textPrimary
                width: parent.width - Theme.spacingSm * 2
                elide: Text.ElideRight
                maximumLineCount: 1
            }

            Text {
                text: root.actorsKo || ""
                font.pixelSize: Theme.fontCaption - 1
                color: Theme.textSecondary
                width: parent.width - Theme.spacingSm * 2
                elide: Text.ElideRight
                maximumLineCount: 1
                visible: root.actorsKo !== ""
            }

            Row {
                spacing: 4

                StatusBadge {
                    visible: root.hasJaSrt
                    status: "transcription"
                    label: "S"
                }

                StatusBadge {
                    visible: root.hasKoSrt
                    status: "translation"
                    label: "B"
                }

                StatusBadge {
                    visible: root.lampHardcoded
                    status: "canonical"
                    label: "자"
                }

                StatusBadge {
                    visible: root.partCount > 1
                    status: "queued"
                    label: "P" + root.partCount
                }

                Text {
                    visible: root.sceneCount > 0
                    text: root.sceneCount + " scenes"
                    font.pixelSize: Theme.fontCaption - 2
                    color: Theme.textMuted
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
        }
    }
}
