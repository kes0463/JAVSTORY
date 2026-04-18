import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components"

ApplicationWindow {
    id: window
    visible: true
    width: 1280
    height: 820
    minimumWidth: 900
    minimumHeight: 600
    title: "JAVSTORY Pro"
    color: Theme.bgPrimary

    // ── 토스트 알림 ─────────────────────────────────
    ToastNotification {
        id: toast
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: Theme.spacingLg
        z: 100
    }

    FolderBindingReviewPopup {
        id: folderBindingReviewPopup
    }

    // 전역 토스트 헬퍼 (Python 모델에서 호출)
    function showToast(msg, level) {
        toast.show(msg, level || "info");
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // ── 사이드바 ────────────────────────────────
        NavSidebar {
            id: sidebar
            Layout.fillHeight: true

            onNavigate: function(idx) {
                viewStack.currentIndex = idx;
            }
        }

        // ── 메인 컨텐츠 ─────────────────────────────
        StackLayout {
            id: viewStack
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: 0

            Loader {
                source: "views/DashboardView.qml"
                asynchronous: true
            }
            Loader {
                source: "views/HarvestView.qml"
                asynchronous: true
            }
            Loader {
                source: "views/ProcessingView.qml"
                asynchronous: true
            }
            Loader {
                id: libraryLoader
                source: "views/LibraryView.qml"
                asynchronous: true
                onLoaded: {
                    if (viewStack.currentIndex === 3 && item)
                        item.forceLibraryFocus()
                }
            }
            Loader {
                source: "views/SettingsView.qml"
                asynchronous: true
            }
        }
    }

    Connections {
        target: viewStack
        function onCurrentIndexChanged() {
            if (viewStack.currentIndex === 3 && libraryLoader.item)
                libraryLoader.item.forceLibraryFocus()
        }
    }

    Connections {
        target: LibraryModel
        function onFolderBindingNeedsReview(productCode, oldPath, candidates) {
            folderBindingReviewPopup.productCode = productCode || ""
            folderBindingReviewPopup.oldPath = oldPath || ""
            folderBindingReviewPopup.candidates = candidates ? candidates : []
            folderBindingReviewPopup.open()
        }
    }
}
