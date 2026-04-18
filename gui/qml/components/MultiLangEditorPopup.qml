import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

Popup {
    id: root
    modal: true
    focus: true
    padding: Theme.spacingMd
    parent: Overlay.overlay
    anchors.centerIn: Overlay.overlay
    width: Math.min(560, Overlay.overlay.width - 48)

    property string editMode: "title" // "title" | "synopsis"

    function reloadFields() {
        if (editMode === "title") {
            tfKo.text = LibraryModel.editDraft.titleKo
            tfJa.text = LibraryModel.editDraft.titleJa
            tfEn.text = LibraryModel.editDraft.titleEn
            tfZhc.text = LibraryModel.editDraft.titleZhCn
            tfZht.text = LibraryModel.editDraft.titleZhTw
        } else {
            tfKo.text = LibraryModel.editDraft.synopsisKo
            tfJa.text = LibraryModel.editDraft.synopsisJa
            tfEn.text = LibraryModel.editDraft.synopsisEn
            tfZhc.text = LibraryModel.editDraft.synopsisZhCn
            tfZht.text = LibraryModel.editDraft.synopsisZhTw
        }
    }

    function applyAndClose() {
        if (editMode === "title") {
            LibraryModel.setDraftTitles(tfKo.text, tfJa.text, tfEn.text, tfZhc.text, tfZht.text)
        } else {
            LibraryModel.setDraftSynopses(tfKo.text, tfJa.text, tfEn.text, tfZhc.text, tfZht.text)
        }
        close()
    }

    onOpened: reloadFields()

    background: Rectangle {
        radius: Theme.radiusMd
        color: Theme.surface
        border.color: Theme.glassBorder
        border.width: 1
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: Theme.spacingSm

        Text {
            text: editMode === "title" ? "제목 (다국어)" : "시놉시스 (다국어)"
            font.pixelSize: Theme.fontSubtitle
            font.weight: Font.DemiBold
            color: Theme.textPrimary
            Layout.fillWidth: true
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.preferredHeight: 420
            clip: true

            ColumnLayout {
                width: parent.width
                spacing: Theme.spacingSm

                Label { text: "한국어"; color: Theme.textMuted; font.pixelSize: Theme.fontCaption }
                TextArea { id: tfKo; Layout.fillWidth: true; wrapMode: TextArea.Wrap; selectByMouse: true }

                Label { text: "일본어"; color: Theme.textMuted; font.pixelSize: Theme.fontCaption }
                TextArea { id: tfJa; Layout.fillWidth: true; wrapMode: TextArea.Wrap; selectByMouse: true }

                Label { text: "영어"; color: Theme.textMuted; font.pixelSize: Theme.fontCaption }
                TextArea { id: tfEn; Layout.fillWidth: true; wrapMode: TextArea.Wrap; selectByMouse: true }

                Label { text: "중국어 간체"; color: Theme.textMuted; font.pixelSize: Theme.fontCaption }
                TextArea { id: tfZhc; Layout.fillWidth: true; wrapMode: TextArea.Wrap; selectByMouse: true }

                Label { text: "중국어 번체"; color: Theme.textMuted; font.pixelSize: Theme.fontCaption }
                TextArea { id: tfZht; Layout.fillWidth: true; wrapMode: TextArea.Wrap; selectByMouse: true }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd
            Item { Layout.fillWidth: true }
            Button {
                text: "취소"
                flat: true
                onClicked: root.close()
            }
            Button {
                text: "확인"
                highlighted: true
                onClicked: root.applyAndClose()
            }
        }
    }
}
