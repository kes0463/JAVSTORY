import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."
import "../components"

Item {
    id: root

    ScrollView {
        id: scrollView
        anchors.fill: parent
        anchors.margins: Theme.spacingLg
        contentWidth: availableWidth
        Component.onCompleted: {
            var f = scrollView.contentItem
            if (f) {
                f.flickDeceleration = Theme.flickDeceleration
                f.maximumFlickVelocity = Theme.maxVelocity
                f.boundsBehavior = Theme.boundsBehavior
            }
        }

        Column {
            width: parent.width
            spacing: Theme.spacingLg

            // ── 헤더 ────────────────────────────────────
            Column {
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

            // ── GPU / CPU 모니터 ────────────────────────
            Row {
                spacing: Theme.spacingMd
                width: parent.width

                GlassCard {
                    width: (parent.width - Theme.spacingMd) / 2
                    height: 180

                    Column {
                        anchors.fill: parent
                        anchors.margins: Theme.spacingMd
                        spacing: Theme.spacingSm

                        Text {
                            text: "GPU VRAM"
                            font.pixelSize: Theme.fontSubtitle
                            font.weight: Font.DemiBold
                            color: Theme.textPrimary
                        }

                        Row {
                            spacing: Theme.spacingMd

                            ProgressIndicator {
                                circular: true
                                width: 72; height: 72
                                value: DashboardModel.gpuUsagePercent / 100
                                barColor: DashboardModel.gpuUsagePercent > 80 ? Theme.error
                                        : DashboardModel.gpuUsagePercent > 50 ? Theme.warning
                                        : Theme.accentNeon
                            }

                            Column {
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 4

                                Text {
                                    text: DashboardModel.gpuName || "GPU 미감지"
                                    font.pixelSize: Theme.fontBody
                                    color: Theme.textSecondary
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
                }

                GlassCard {
                    width: (parent.width - Theme.spacingMd) / 2
                    height: 180

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

                        Column {
                            spacing: Theme.spacingSm
                            width: parent.width

                            Row {
                                spacing: Theme.spacingSm
                                Text { text: "CPU"; width: 50; font.pixelSize: Theme.fontCaption; color: Theme.textSecondary; anchors.verticalCenter: parent.verticalCenter }
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
                                Text { text: "MEM"; width: 50; font.pixelSize: Theme.fontCaption; color: Theme.textSecondary; anchors.verticalCenter: parent.verticalCenter }
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
            }

            // ── 작업 큐 ─────────────────────────────────
            GlassCard {
                width: parent.width
                height: Math.max(200, queueList.contentHeight + 60)

                Column {
                    anchors.fill: parent
                    anchors.margins: Theme.spacingMd
                    spacing: Theme.spacingSm

                    Row {
                        spacing: Theme.spacingSm
                        Text {
                            text: "대기 큐"
                            font.pixelSize: Theme.fontSubtitle
                            font.weight: Font.DemiBold
                            color: Theme.textPrimary
                        }
                        StatusBadge {
                            status: DashboardModel.pendingCount > 0 ? "running" : "none"
                            label: DashboardModel.pendingCount + "건"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    ListView {
                        id: queueList
                        width: parent.width
                        height: parent.height - 40
                        clip: true
                        model: DashboardModel.pendingQueue
                        boundsBehavior: Theme.boundsBehavior
                        flickDeceleration: Theme.flickDeceleration
                        maximumFlickVelocity: Theme.maxVelocity

                        delegate: Rectangle {
                            width: queueList.width
                            height: 36
                            color: index % 2 === 0 ? "transparent" : Qt.rgba(255/255, 255/255, 255/255, 0.02)
                            radius: 4

                            Row {
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: parent.left
                                anchors.leftMargin: Theme.spacingSm
                                spacing: Theme.spacingSm

                                Text {
                                    text: model.sku
                                    font.pixelSize: Theme.fontCaption
                                    font.weight: Font.Bold
                                    color: Theme.accentNeon
                                    width: 100
                                }
                                Text {
                                    text: model.title
                                    font.pixelSize: Theme.fontCaption
                                    color: Theme.textSecondary
                                    elide: Text.ElideRight
                                    width: 400
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
        }
    }
}
