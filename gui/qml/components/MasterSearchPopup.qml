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
    width: Math.min(440, Overlay.overlay.width - 48)

    property string pickerMode: "maker" // maker | genre | actress

    ListModel { id: pickModel }

    function refresh() {
        var q = searchField.text
        var arr
        if (pickerMode === "maker")
            arr = LibraryModel.searchMakers(q)
        else if (pickerMode === "genre")
            arr = LibraryModel.searchGenres(q)
        else
            arr = LibraryModel.searchActresses(q)

        pickModel.clear()
        for (var i = 0; i < arr.length; i++) {
            var o = arr[i]
            pickModel.append({
                line: pickerMode === "maker"
                    ? ((o.japanese || "") + " — " + (o.korean || "") + " — " + (o.english || ""))
                    : (pickerMode === "genre"
                        ? ((o.japanese || "") + " — " + (o.korean || ""))
                        : ((o.japanese || "") + " — " + (o.korean || "") + " — " + (o.romaji || ""))),
                jp: o.japanese || "",
                ko: o.korean || "",
                en: o.english || "",
                romaji: o.romaji || ""
            })
        }
    }

    onOpened: {
        searchField.text = ""
        refresh()
    }

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
            text: pickerMode === "maker" ? "메이커 선택"
                : (pickerMode === "genre" ? "장르 선택" : "배우 선택")
            font.pixelSize: Theme.fontSubtitle
            font.weight: Font.DemiBold
            color: Theme.textPrimary
            Layout.fillWidth: true
        }

        TextField {
            id: searchField
            Layout.fillWidth: true
            placeholderText: "검색…"
            selectByMouse: true
            onTextChanged: debounce.restart()
        }

        Timer {
            id: debounce
            interval: 200
            repeat: false
            onTriggered: root.refresh()
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.preferredHeight: 280
            clip: true

            ListView {
                model: pickModel
                spacing: 4

                delegate: ItemDelegate {
                    width: ListView.view.width
                    text: model.line
                    onClicked: {
                        if (pickerMode === "maker") {
                            LibraryModel.applyMakerFields(model.jp, model.ko, model.en)
                        } else if (pickerMode === "genre") {
                            LibraryModel.appendGenreKo(model.ko || model.jp)
                        } else {
                            LibraryModel.appendActorKo(model.ko || model.jp)
                        }
                        root.close()
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd
            Button {
                text: pickerMode === "maker" ? "새 메이커 추가…"
                    : (pickerMode === "genre" ? "새 장르 추가…" : "새 배우 추가…")
                flat: true
                onClicked: {
                    root.close()
                    newEntryPopup.open()
                }
            }
            Item { Layout.fillWidth: true }
            Button {
                text: "닫기"
                onClicked: root.close()
            }
        }
    }

    Popup {
        id: newEntryPopup
        modal: true
        focus: true
        padding: Theme.spacingMd
        parent: Overlay.overlay
        anchors.centerIn: Overlay.overlay
        width: Math.min(400, Overlay.overlay.width - 48)

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
                text: pickerMode === "maker" ? "새 메이커" : (pickerMode === "genre" ? "새 장르" : "새 배우")
                font.pixelSize: Theme.fontSubtitle
                font.weight: Font.DemiBold
                color: Theme.textPrimary
            }

            Label { text: "일본어"; color: Theme.textMuted; font.pixelSize: Theme.fontCaption }
            TextField { id: njJa; Layout.fillWidth: true; selectByMouse: true }

            Label { text: "한국어"; color: Theme.textMuted; font.pixelSize: Theme.fontCaption }
            TextField { id: njKo; Layout.fillWidth: true; selectByMouse: true }

            Label {
                visible: pickerMode === "maker"
                text: "영어 (slug)"
                color: Theme.textMuted
                font.pixelSize: Theme.fontCaption
            }
            TextField {
                id: njEn
                visible: pickerMode === "maker"
                Layout.fillWidth: true
                selectByMouse: true
            }

            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Button {
                    text: "취소"
                    flat: true
                    onClicked: newEntryPopup.close()
                }
                Button {
                    text: "추가"
                    highlighted: true
                    onClicked: {
                        if (pickerMode === "maker") {
                            LibraryModel.insertNewMaker(njJa.text, njKo.text, njEn.text)
                        } else if (pickerMode === "genre") {
                            LibraryModel.insertNewGenre(njJa.text, njKo.text)
                        } else {
                            LibraryModel.insertNewActress(njJa.text, njKo.text)
                        }
                        newEntryPopup.close()
                    }
                }
            }
        }
    }
}
