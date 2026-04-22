import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components"

ApplicationWindow {
    id: window
    visible: true
    /** 수집 탭 도구줄(SearchBar·버튼 줄)이 사이드바(260)+여백까지 포함해 한 줄로 보이도록 여유 너비 */
    width: 1540
    height: 980
    minimumWidth: 1340
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
        onResolved: function (productCode) {
            removeFolderBindingFromInbox(productCode)
        }
    }

    ListModel {
        id: folderBindingInboxModel
    }

    /** ListModel은 배열 role를 넣으면 깨지므로 후보 경로는 JSON 문자열로 저장 */
    function candidatesToJson(candidates) {
        if (!candidates)
            return "[]"
        if (typeof candidates === "string") {
            try {
                var chk = JSON.parse(candidates)
                return Array.isArray(chk) ? candidates : "[]"
            } catch (e1) {
                return "[]"
            }
        }
        try {
            return JSON.stringify(candidates)
        } catch (e2) {
            return "[]"
        }
    }

    function inboxModelToPersistentJson() {
        var out = []
        for (var i = 0; i < folderBindingInboxModel.count; i++) {
            var row = folderBindingInboxModel.get(i)
            var paths = []
            try {
                var raw = JSON.parse(row.candidatesJson || "[]")
                paths = Array.isArray(raw) ? raw : []
            } catch (e0) {
                paths = []
            }
            out.push({
                product_code: row.productCode || "",
                old_path: row.oldPath || "",
                candidates: paths
            })
        }
        return JSON.stringify(out)
    }

    function persistFolderBindingInbox() {
        FolderBindingInboxStore.saveJson(inboxModelToPersistentJson())
    }

    /** skipPersist=true: 배치 로드 시 디스크 쓰기 생략 */
    function upsertFolderBindingInbox(productCode, oldPath, candidates, skipPersist) {
        var pc = productCode || ""
        var op = oldPath || ""
        var j = candidatesToJson(candidates)
        for (var i = 0; i < folderBindingInboxModel.count; i++) {
            if (folderBindingInboxModel.get(i).productCode === pc) {
                folderBindingInboxModel.set(i, {
                    "productCode": pc,
                    "oldPath": op,
                    "candidatesJson": j
                })
                if (skipPersist !== true)
                    persistFolderBindingInbox()
                return
            }
        }
        folderBindingInboxModel.append({
            "productCode": pc,
            "oldPath": op,
            "candidatesJson": j
        })
        if (skipPersist !== true)
            persistFolderBindingInbox()
    }

    function removeFolderBindingFromInbox(productCode, skipPersist) {
        var pc = productCode || ""
        for (var i = folderBindingInboxModel.count - 1; i >= 0; i--) {
            if (folderBindingInboxModel.get(i).productCode === pc)
                folderBindingInboxModel.remove(i)
        }
        if (skipPersist !== true)
            persistFolderBindingInbox()
    }

    function clearFolderBindingInbox(skipPersist) {
        while (folderBindingInboxModel.count > 0)
            folderBindingInboxModel.remove(0)
        if (skipPersist !== true)
            persistFolderBindingInbox()
    }

    function loadPersistedInbox() {
        var s = FolderBindingInboxStore.loadJson()
        if (!s)
            return
        try {
            var arr = JSON.parse(s)
            if (!Array.isArray(arr))
                return
            while (folderBindingInboxModel.count > 0)
                folderBindingInboxModel.remove(0)
            for (var i = 0; i < arr.length; i++) {
                var e = arr[i]
                var pc = e.product_code !== undefined ? e.product_code : (e.productCode || "")
                var op = e.old_path !== undefined ? e.old_path : (e.oldPath || "")
                upsertFolderBindingInbox(pc, op, e.candidates, true)
            }
            persistFolderBindingInbox()
        } catch (err) {
            console.warn("folder binding inbox load:", err)
        }
    }

    Component.onCompleted: loadPersistedInbox()

    FolderBindingInboxDrawer {
        id: folderBindingInboxDrawer
        z: 80
        height: window.height
        inboxModel: folderBindingInboxModel
        onDetailRequested: function (pc, op, cands) {
            folderBindingReviewPopup.productCode = pc || ""
            folderBindingReviewPopup.oldPath = op || ""
            folderBindingReviewPopup.candidates = Array.isArray(cands) ? cands : []
            folderBindingReviewPopup.open()
        }
        onRemoveRequested: function (pc) {
            removeFolderBindingFromInbox(pc)
        }
        onClearRequested: clearFolderBindingInbox()
    }

    // 전역 토스트 헬퍼 (Python 모델에서 호출)
    function showToast(msg, level) {
        toast.show(msg, level || "info");
    }

    Connections {
        target: HighlightQueue
        function onToastMessage(msg, level) { window.showToast(msg, level); }
    }

    Connections {
        target: PreviewQueue
        function onToastMessage(msg, level) { window.showToast(msg, level); }
    }

    Connections {
        target: MontageQueue
        function onToastMessage(msg, level) { window.showToast(msg, level); }
    }
    
    Connections {
        target: MosaicQueue
        function onToastMessage(msg, level) { window.showToast(msg, level); }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // ── 사이드바 ────────────────────────────────
        NavSidebar {
            id: sidebar
            Layout.fillHeight: true
            folderAlertCount: folderBindingInboxModel.count

            onNavigate: function(idx) {
                viewStack.currentIndex = idx;
            }
            onOpenFolderAlerts: folderBindingInboxDrawer.open()
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
            upsertFolderBindingInbox(productCode, oldPath, candidates)
            window.showToast(
                "폴더 연결 확인 대기: " + (productCode || "")
                + " — 사이드바 「폴더 알림」에서 모아 볼 수 있습니다.",
                "info")
        }
    }
}
