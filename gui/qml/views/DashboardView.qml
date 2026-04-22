import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."
import "../components"

Item {
    id: root

    // ── 큐 섹션 공통 컴포넌트 ──────────────────────────────
    component QueueSection: Item {
        id: queueSectionRoot

        property string title: ""
        property alias headerContent: headerRow.data     // 헤더 Row 에 추가 버튼 등 삽입용
        property alias listModel: innerList.model
        property string emptyText: "대기/진행 항목이 없습니다."
        property Component delegateComp: null

        clip: true

        Column {
            id: queueSectionCol
            anchors.fill: parent
            anchors.margins: Theme.spacingMd
            spacing: Theme.spacingSm

            // 타이틀 행
            Row {
                id: headerRow
                spacing: Theme.spacingSm
                width: parent.width
            }

            // 큐 목록
            ListView {
                id: innerList
                width: parent.width
                // 남은 높이에서 타이틀 행 높이 빼기
                height: Math.max(0, queueSectionCol.height - headerRow.height - Theme.spacingSm)
                clip: true
                boundsBehavior: Theme.boundsBehavior
                flickDeceleration: Theme.flickDeceleration
                maximumFlickVelocity: Theme.maxVelocity
                delegate: queueSectionRoot.delegateComp

                Text {
                    visible: innerList.count === 0
                    anchors.centerIn: parent
                    text: queueSectionRoot.emptyText
                    font.pixelSize: Theme.fontBody
                    color: Theme.textMuted
                }
            }
        }
    }

    // ── 삭제 버튼 컴포넌트 ─────────────────────────────────
    component DeleteButton: Item {
        id: delBtnRoot
        width: 24; height: 24
        signal clicked()

        Rectangle {
            anchors.fill: parent
            radius: 4
            color: mouseArea.containsMouse ? Qt.rgba(1, 0, 0, 0.1) : "transparent"
            Behavior on color { ColorAnimation { duration: 100 } }

            Text {
                anchors.centerIn: parent
                text: "✕"
                font.pixelSize: 14
                color: mouseArea.containsMouse ? Theme.error : Theme.textMuted
                Behavior on color { ColorAnimation { duration: 100 } }
            }
        }

        MouseArea {
            id: mouseArea
            anchors.fill: parent
            hoverEnabled: true
            onClicked: delBtnRoot.clicked()
        }
    }

    // ── 메인 레이아웃 ──────────────────────────────────────
    ScrollView {
        anchors.fill: parent
        contentWidth: availableWidth

        ColumnLayout {
            id: layout
            width: parent.width
            spacing: Theme.spacingLg

            // ── 헤더 ─────────────────────────────────────
            Column {
                Layout.fillWidth: true
                Layout.topMargin: Theme.spacingLg
                Layout.leftMargin: Theme.spacingLg
                Layout.rightMargin: Theme.spacingLg
                spacing: 4

                Text {
                    text: "JAVSTORY Pro"
                    font.pixelSize: Theme.fontDisplay
                    font.weight: Font.ExtraBold
                    color: Theme.textPrimary
                }
                Text {
                    text: "시스템 리소스 및 작업 현황"
                    font.pixelSize: Theme.fontBody
                    color: Theme.textSecondary
                }
            }

            // ── GPU / CPU 모니터 ──────────────────────────
            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: Theme.spacingLg
                Layout.rightMargin: Theme.spacingLg
                spacing: Theme.spacingMd

                GlassCard {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 120

                    Row {
                        anchors.fill: parent
                        anchors.margins: Theme.spacingMd
                        spacing: Theme.spacingMd

                        ProgressIndicator {
                            circular: true
                            width: 72; height: 72
                            anchors.verticalCenter: parent.verticalCenter
                            value: DashboardModel.gpuUsagePercent / 100
                            barColor: DashboardModel.gpuUsagePercent > 80 ? Theme.error
                                    : DashboardModel.gpuUsagePercent > 50 ? Theme.warning
                                    : Theme.accentNeon
                        }

                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 6

                            Text {
                                text: "GPU VRAM"
                                font.pixelSize: Theme.fontSubtitle
                                font.weight: Font.DemiBold
                                color: Theme.textPrimary
                            }
                            Text {
                                text: DashboardModel.gpuName || "GPU 미감지"
                                font.pixelSize: Theme.fontCaption
                                color: Theme.textSecondary
                                elide: Text.ElideRight
                                width: 160
                            }
                            Text {
                                text: DashboardModel.gpuUsed.toFixed(1) + " GB / " + DashboardModel.gpuTotal.toFixed(1) + " GB"
                                font.pixelSize: Theme.fontBody
                                font.weight: Font.DemiBold
                                color: Theme.textPrimary
                            }
                        }
                    }
                }

                GlassCard {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 120

                    Column {
                        anchors.fill: parent
                        anchors.margins: Theme.spacingMd
                        spacing: Theme.spacingSm

                        Text {
                            text: "시스템"
                            font.pixelSize: Theme.fontSubtitle
                            font.weight: Font.DemiBold
                            color: Theme.textPrimary
                        }

                        Row {
                            spacing: Theme.spacingSm
                            width: parent.width
                            Text { text: "CPU"; width: 44; font.pixelSize: Theme.fontCaption; color: Theme.textSecondary; anchors.verticalCenter: parent.verticalCenter }
                            ProgressIndicator {
                                width: 140
                                value: DashboardModel.cpuPercent / 100
                                barColor: Theme.primaryBlue
                            }
                            Text {
                                text: DashboardModel.cpuPercent + "%"
                                font.pixelSize: Theme.fontCaption
                                font.weight: Font.DemiBold
                                color: Theme.textPrimary
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        Row {
                            spacing: Theme.spacingSm
                            width: parent.width
                            Text { text: "MEM"; width: 44; font.pixelSize: Theme.fontCaption; color: Theme.textSecondary; anchors.verticalCenter: parent.verticalCenter }
                            ProgressIndicator {
                                width: 140
                                value: DashboardModel.memPercent / 100
                                barColor: Theme.accentNeon
                            }
                            Text {
                                text: DashboardModel.memUsed.toFixed(1) + " / " + DashboardModel.memTotal.toFixed(1) + " GB"
                                font.pixelSize: Theme.fontCaption
                                font.weight: Font.DemiBold
                                color: Theme.textPrimary
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                    }
                }
            }

            // ── 대기 큐 ──────────────────────────────────
            GlassCard {
                id: pendingCard
                property bool expanded: false
                Layout.fillWidth: true
                Layout.leftMargin: Theme.spacingLg
                Layout.rightMargin: Theme.spacingLg
                Layout.preferredHeight: expanded ? 400 : 150
                Behavior on Layout.preferredHeight { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
                clip: true

                Column {
                    anchors.fill: parent
                    anchors.margins: Theme.spacingMd
                    spacing: Theme.spacingSm

                    Row {
                        spacing: Theme.spacingSm
                        width: parent.width
                        Text {
                            text: "대기 큐"
                            font.pixelSize: Theme.fontSubtitle
                            font.weight: Font.DemiBold
                            color: Theme.textPrimary
                        }
                        Text {
                            text: pendingCard.expanded ? "▲" : "▼"
                            font.pixelSize: 10
                            color: Theme.textMuted
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        MouseArea {
                            anchors.fill: parent
                            onClicked: pendingCard.expanded = !pendingCard.expanded
                        }
                    }
                    Row {
                        Layout.fillWidth: true
                        spacing: Theme.spacingSm
                        StatusBadge {
                            status: DashboardModel.pendingCount > 0 ? "running" : "none"
                            label: DashboardModel.pendingCount + "건"
                        }
                        Item { Layout.fillWidth: true; height: 1 }
                        ActionButton {
                            text: "큐 비우기"
                            primary: false
                            onClicked: DashboardModel.clearAllPending()
                            visible: DashboardModel.pendingCount > 0
                        }
                    }

                    ListView {
                        id: queueList
                        width: parent.width
                        height: parent.height - 28 - Theme.spacingSm
                        clip: true
                        model: DashboardModel.pendingQueue
                        boundsBehavior: Theme.boundsBehavior
                        flickDeceleration: Theme.flickDeceleration
                        maximumFlickVelocity: Theme.maxVelocity

                        delegate: Rectangle {
                            width: queueList.width
                            height: 36
                            color: index % 2 === 0 ? "transparent" : Qt.rgba(1, 1, 1, 0.02)
                            radius: 4
                            clip: true

                            Row {
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.leftMargin: Theme.spacingSm
                                anchors.rightMargin: Theme.spacingSm
                                spacing: Theme.spacingSm

                                Text {
                                    text: model.sku
                                    font.pixelSize: Theme.fontCaption
                                    font.weight: Font.Bold
                                    color: Theme.accentNeon
                                    width: 100
                                    elide: Text.ElideRight
                                }
                                Text {
                                    text: model.title
                                    font.pixelSize: Theme.fontCaption
                                    color: Theme.textSecondary
                                    elide: Text.ElideRight
                                    width: queueList.width - 100 - 24 - Theme.spacingSm * 4
                                }
                                DeleteButton {
                                    anchors.verticalCenter: parent.verticalCenter
                                    onClicked: DashboardModel.cancelPending(model.sku)
                                }
                            }
                        }

                        Text {
                            visible: queueList.count === 0
                            anchors.centerIn: parent
                            text: "대기 중인 항목이 없습니다."
                            font.pixelSize: Theme.fontBody
                            color: Theme.textMuted
                        }
                    }
                }
            }

            // ── 하이라이트 큐 ─────────────────────────────
            GlassCard {
                id: highlightCard
                property bool expanded: false
                Layout.fillWidth: true
                Layout.leftMargin: Theme.spacingLg
                Layout.rightMargin: Theme.spacingLg
                Layout.preferredHeight: expanded ? 400 : 180
                Behavior on Layout.preferredHeight { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
                clip: true

                Column {
                    anchors.fill: parent
                    anchors.margins: Theme.spacingMd
                    spacing: Theme.spacingSm

                    Row {
                        spacing: Theme.spacingSm
                        width: parent.width
                        Text {
                            text: "하이라이트 큐"
                            font.pixelSize: Theme.fontSubtitle
                            font.weight: Font.DemiBold
                            color: Theme.textPrimary
                        }
                        Text {
                            text: highlightCard.expanded ? "▲" : "▼"
                            font.pixelSize: 10
                            color: Theme.textMuted
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        MouseArea {
                            anchors.fill: parent
                            onClicked: highlightCard.expanded = !highlightCard.expanded
                        }
                    }
                    Row {
                        Layout.fillWidth: true
                        spacing: Theme.spacingSm
                        StatusBadge {
                            status: HighlightQueue.pendingCount > 0 ? "running" : "none"
                            label: HighlightQueue.runningCount + " 실행 / " + HighlightQueue.pendingCount + " 대기"
                        }
                        Item { Layout.fillWidth: true; height: 1 }
                        ActionButton {
                            text: "완료 제거"
                            primary: false
                            onClicked: HighlightQueue.clearFinished()
                        }
                    }

                    ListView {
                        id: highlightQueueList
                        width: parent.width
                        height: parent.height - 28 - Theme.spacingSm
                        clip: true
                        model: HighlightQueue.queue
                        boundsBehavior: Theme.boundsBehavior
                        flickDeceleration: Theme.flickDeceleration
                        maximumFlickVelocity: Theme.maxVelocity

                        delegate: Rectangle {
                            width: highlightQueueList.width
                            height: 46
                            color: index % 2 === 0 ? "transparent" : Qt.rgba(1, 1, 1, 0.02)
                            radius: 4
                            clip: true

                            RowLayout {
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.leftMargin: Theme.spacingSm
                                anchors.rightMargin: Theme.spacingSm
                                spacing: Theme.spacingSm

                                Text {
                                    text: model.productCode
                                    font.pixelSize: Theme.fontCaption
                                    font.weight: Font.Bold
                                    color: Theme.accentNeon
                                    Layout.preferredWidth: 90
                                    elide: Text.ElideRight
                                }
                                Text {
                                    text: model.videoName
                                    font.pixelSize: Theme.fontCaption
                                    color: Theme.textSecondary
                                    elide: Text.ElideMiddle
                                    Layout.fillWidth: true
                                }
                                ProgressIndicator {
                                    Layout.preferredWidth: 140
                                    value: (model.progress || 0) / 100
                                    barHeight: 6
                                    barColor: model.status === "error" ? Theme.error
                                            : model.status === "done"  ? Theme.accentNeon
                                            : Theme.primaryBlue
                                }
                                Text {
                                    text: model.status === "queued"  ? "대기"
                                        : model.status === "running" ? (model.progress + "%")
                                        : model.status === "done"   ? "완료"
                                        : "실패"
                                    font.pixelSize: Theme.fontCaption
                                    font.weight: Font.DemiBold
                                    color: model.status === "error" ? Theme.error
                                         : model.status === "done"  ? Theme.accentNeon
                                         : Theme.textPrimary
                                    Layout.preferredWidth: 40
                                    horizontalAlignment: Text.AlignRight
                                }
                                DeleteButton {
                                    Layout.preferredWidth: 24
                                    Layout.preferredHeight: 24
                                    onClicked: HighlightQueue.removeJob(model.jobId)
                                }
                            }
                        }

                        Text {
                            visible: highlightQueueList.count === 0
                            anchors.centerIn: parent
                            text: "하이라이트 대기/진행 항목이 없습니다."
                            font.pixelSize: Theme.fontBody
                            color: Theme.textMuted
                        }
                    }
                }
            }

            // ── 프리뷰 큐 ─────────────────────────────────
            GlassCard {
                id: previewCard
                property bool expanded: false
                Layout.fillWidth: true
                Layout.leftMargin: Theme.spacingLg
                Layout.rightMargin: Theme.spacingLg
                Layout.preferredHeight: expanded ? 400 : 180
                Behavior on Layout.preferredHeight { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
                clip: true

                Column {
                    anchors.fill: parent
                    anchors.margins: Theme.spacingMd
                    spacing: Theme.spacingSm

                    Row {
                        spacing: Theme.spacingSm
                        width: parent.width
                        clip: true

                        Text {
                            text: "프리뷰 큐"
                            font.pixelSize: Theme.fontSubtitle
                            font.weight: Font.DemiBold
                            color: Theme.textPrimary
                        }
                        Text {
                            text: previewCard.expanded ? "▲" : "▼"
                            font.pixelSize: 10
                            color: Theme.textMuted
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        MouseArea {
                            anchors.fill: parent
                            onClicked: previewCard.expanded = !previewCard.expanded
                        }
                    }
                    Row {
                        Layout.fillWidth: true
                        spacing: Theme.spacingSm
                        StatusBadge {
                            status: PreviewQueue.pendingCount > 0 ? "running" : "none"
                            label: PreviewQueue.runningCount + " 실행 / " + PreviewQueue.pendingCount + " 대기"
                        }
                        Item { width: 12; height: 1 }
                        ActionButton {
                            text: "백필"
                            primary: false
                            onClicked: PreviewQueue.enqueueMissingPreviews()
                        }
                        ActionButton {
                            text: "일괄 재생성"
                            primary: false
                            onClicked: PreviewQueue.enqueueAllPreviewsForce()
                        }
                        Item { Layout.fillWidth: true; height: 1 }
                        ActionButton {
                            text: "완료 제거"
                            primary: false
                            onClicked: PreviewQueue.clearFinished()
                        }
                    }

                    ListView {
                        id: previewQueueList
                        width: parent.width
                        height: parent.height - 36 - Theme.spacingSm
                        clip: true
                        model: PreviewQueue.queue
                        boundsBehavior: Theme.boundsBehavior
                        flickDeceleration: Theme.flickDeceleration
                        maximumFlickVelocity: Theme.maxVelocity

                        delegate: Rectangle {
                            width: previewQueueList.width
                            height: 46
                            color: index % 2 === 0 ? "transparent" : Qt.rgba(1, 1, 1, 0.02)
                            radius: 4
                            clip: true

                            RowLayout {
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.leftMargin: Theme.spacingSm
                                anchors.rightMargin: Theme.spacingSm
                                spacing: Theme.spacingSm

                                Text {
                                    text: model.productCode
                                    font.pixelSize: Theme.fontCaption
                                    font.weight: Font.Bold
                                    color: Theme.accentNeon
                                    Layout.preferredWidth: 90
                                    elide: Text.ElideRight
                                }
                                Text {
                                    text: model.videoName
                                    font.pixelSize: Theme.fontCaption
                                    color: Theme.textSecondary
                                    elide: Text.ElideMiddle
                                    Layout.fillWidth: true
                                }
                                ProgressIndicator {
                                    Layout.preferredWidth: 140
                                    value: (model.progress || 0) / 100
                                    barHeight: 6
                                    barColor: model.status === "error" ? Theme.error
                                            : model.status === "done"  ? Theme.accentNeon
                                            : Theme.primaryBlue
                                }
                                Text {
                                    text: model.status === "queued"  ? "대기"
                                        : model.status === "running" ? (model.progress + "%")
                                        : model.status === "done"   ? "완료"
                                        : "실패"
                                    font.pixelSize: Theme.fontCaption
                                    font.weight: Font.DemiBold
                                    color: model.status === "error" ? Theme.error
                                         : model.status === "done"  ? Theme.accentNeon
                                         : Theme.textPrimary
                                    Layout.preferredWidth: 40
                                    horizontalAlignment: Text.AlignRight
                                }
                                DeleteButton {
                                    Layout.preferredWidth: 24
                                    Layout.preferredHeight: 24
                                    onClicked: PreviewQueue.removeJob(model.jobId)
                                }
                            }
                        }

                        Text {
                            visible: previewQueueList.count === 0
                            anchors.centerIn: parent
                            text: "프리뷰 대기/진행 항목이 없습니다."
                            font.pixelSize: Theme.fontBody
                            color: Theme.textMuted
                        }
                    }
                }
            }

            // ── 몽타주 큐 ─────────────────────────────────
            GlassCard {
                id: montageCard
                property bool expanded: false
                Layout.fillWidth: true
                Layout.leftMargin: Theme.spacingLg
                Layout.rightMargin: Theme.spacingLg
                Layout.preferredHeight: expanded ? 400 : 180
                Behavior on Layout.preferredHeight { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
                clip: true

                Column {
                    anchors.fill: parent
                    anchors.margins: Theme.spacingMd
                    spacing: Theme.spacingSm

                    Row {
                        spacing: Theme.spacingSm
                        width: parent.width
                        Text {
                            text: "몽타주 큐"
                            font.pixelSize: Theme.fontSubtitle
                            font.weight: Font.DemiBold
                            color: Theme.textPrimary
                        }
                        Text {
                            text: montageCard.expanded ? "▲" : "▼"
                            font.pixelSize: 10
                            color: Theme.textMuted
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        MouseArea {
                            anchors.fill: parent
                            onClicked: montageCard.expanded = !montageCard.expanded
                        }
                    }
                    Row {
                        Layout.fillWidth: true
                        spacing: Theme.spacingSm
                        StatusBadge {
                            status: MontageQueue.pendingCount > 0 ? "running" : "none"
                            label: MontageQueue.runningCount + " 실행 / " + MontageQueue.pendingCount + " 대기"
                        }
                        Item { Layout.fillWidth: true; height: 1 }
                        ActionButton {
                            text: "완료 제거"
                            primary: false
                            onClicked: MontageQueue.clearFinished()
                        }
                    }

                    ListView {
                        id: montageQueueList
                        width: parent.width
                        height: parent.height - 28 - Theme.spacingSm
                        clip: true
                        model: MontageQueue.queue
                        boundsBehavior: Theme.boundsBehavior
                        flickDeceleration: Theme.flickDeceleration
                        maximumFlickVelocity: Theme.maxVelocity

                        delegate: Rectangle {
                            width: montageQueueList.width
                            height: 46
                            color: index % 2 === 0 ? "transparent" : Qt.rgba(1, 1, 1, 0.02)
                            radius: 4
                            clip: true

                            RowLayout {
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.leftMargin: Theme.spacingSm
                                anchors.rightMargin: Theme.spacingSm
                                spacing: Theme.spacingSm

                                Text {
                                    text: model.title
                                    font.pixelSize: Theme.fontCaption
                                    font.weight: Font.Bold
                                    color: Theme.accentNeon
                                    Layout.preferredWidth: 140
                                    elide: Text.ElideRight
                                }
                                ProgressIndicator {
                                    Layout.preferredWidth: 140
                                    value: (model.progress || 0) / 100
                                    barHeight: 6
                                    barColor: model.status === "error" ? Theme.error
                                            : model.status === "done"  ? Theme.accentNeon
                                            : Theme.primaryBlue
                                }
                                Text {
                                    text: model.status === "queued"  ? "대기"
                                        : model.status === "running" ? (model.progress + "%")
                                        : model.status === "done"   ? "완료"
                                        : "실패"
                                    font.pixelSize: Theme.fontCaption
                                    font.weight: Font.DemiBold
                                    color: model.status === "error" ? Theme.error
                                         : model.status === "done"  ? Theme.accentNeon
                                         : Theme.textPrimary
                                    Layout.preferredWidth: 40
                                    horizontalAlignment: Text.AlignRight
                                }
                                DeleteButton {
                                    Layout.preferredWidth: 24
                                    Layout.preferredHeight: 24
                                    onClicked: MontageQueue.removeJob(model.jobId)
                                }
                            }
                        }

                        Text {
                            visible: montageQueueList.count === 0
                            anchors.centerIn: parent
                            text: "몽타주 대기/진행 항목이 없습니다."
                            font.pixelSize: Theme.fontBody
                            color: Theme.textMuted
                        }
                    }
                }
            }

            // ── 모자이크 제거 큐 ─────────────────────────────
            GlassCard {
                id: mosaicCard
                property bool expanded: false
                Layout.fillWidth: true
                Layout.leftMargin: Theme.spacingLg
                Layout.rightMargin: Theme.spacingLg
                Layout.bottomMargin: Theme.spacingLg
                Layout.preferredHeight: expanded ? 400 : 180
                Behavior on Layout.preferredHeight { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
                clip: true

                Column {
                    anchors.fill: parent
                    anchors.margins: Theme.spacingMd
                    spacing: Theme.spacingSm

                    Row {
                        spacing: Theme.spacingSm
                        width: parent.width
                        Text {
                            text: "모자이크 제거 큐 (LADA)"
                            font.pixelSize: Theme.fontSubtitle
                            font.weight: Font.DemiBold
                            color: Theme.textPrimary
                        }
                        Text {
                            text: mosaicCard.expanded ? "▲" : "▼"
                            font.pixelSize: 10
                            color: Theme.textMuted
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        MouseArea {
                            anchors.fill: parent
                            onClicked: mosaicCard.expanded = !mosaicCard.expanded
                        }
                        Item { Layout.fillWidth: true; height: 1 }
                        ActionButton {
                            text: "완료 제거"
                            primary: false
                            onClicked: MosaicQueue.clearFinished()
                        }
                    }
                    Row {
                        Layout.fillWidth: true
                        spacing: Theme.spacingSm
                        StatusBadge {
                            status: MosaicQueue.pendingCount > 0 ? "running" : "none"
                            label: MosaicQueue.runningCount + " 실행 / " + MosaicQueue.pendingCount + " 대기"
                        }
                    }

                    ListView {
                        id: mosaicQueueList
                        width: parent.width
                        height: parent.height - (mosaicCard.expanded ? 80 : 56)
                        clip: true
                        model: MosaicQueue.queue
                        boundsBehavior: Theme.boundsBehavior
                        flickDeceleration: Theme.flickDeceleration
                        maximumFlickVelocity: Theme.maxVelocity

                        delegate: Rectangle {
                            width: mosaicQueueList.width
                            height: 46
                            color: index % 2 === 0 ? "transparent" : Qt.rgba(1, 1, 1, 0.02)
                            radius: 4
                            clip: true

                            RowLayout {
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.leftMargin: Theme.spacingSm
                                anchors.rightMargin: Theme.spacingSm
                                spacing: Theme.spacingSm

                                Text {
                                    text: model.productCode
                                    font.pixelSize: Theme.fontCaption
                                    font.weight: Font.Bold
                                    color: Theme.accentNeon
                                    Layout.preferredWidth: 90
                                    elide: Text.ElideRight
                                }
                                Text {
                                    text: model.videoName
                                    font.pixelSize: Theme.fontCaption
                                    color: Theme.textSecondary
                                    elide: Text.ElideMiddle
                                    Layout.fillWidth: true
                                }
                                ProgressIndicator {
                                    Layout.preferredWidth: 140
                                    value: (model.progress || 0) / 100
                                    barHeight: 6
                                    barColor: model.status === "error" ? Theme.error
                                            : model.status === "done"  ? Theme.accentNeon
                                            : Theme.primaryBlue
                                }
                                Text {
                                    text: model.status === "queued"  ? "대기"
                                        : model.status === "running" ? (model.progress + "%")
                                        : model.status === "done"   ? "완료"
                                        : "실패"
                                    font.pixelSize: Theme.fontCaption
                                    font.weight: Font.DemiBold
                                    color: model.status === "error" ? Theme.error
                                         : model.status === "done"  ? Theme.accentNeon
                                         : Theme.textPrimary
                                    Layout.preferredWidth: 40
                                    horizontalAlignment: Text.AlignRight
                                }
                                DeleteButton {
                                    Layout.preferredWidth: 24
                                    Layout.preferredHeight: 24
                                    onClicked: MosaicQueue.removeJob(model.jobId)
                                }
                            }
                        }

                        Text {
                            visible: mosaicQueueList.count === 0
                            anchors.centerIn: parent
                            text: "모자이크 제거 대기/진행 항목이 없습니다."
                            font.pixelSize: Theme.fontBody
                            color: Theme.textMuted
                        }
                    }
                }
            }

        } // ColumnLayout
    } // ScrollView
}
