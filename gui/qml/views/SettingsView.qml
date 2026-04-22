import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."
import "../components"

Item {
    id: root

    Connections {
        target: SettingsModel
        function onToastMessage(msg, level) { window.showToast(msg, level); }
    }

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
            Text {
                text: "설정"
                font.pixelSize: Theme.fontTitle
                font.weight: Font.ExtraBold
                color: Theme.textPrimary
            }

            // ── API 설정 ────────────────────────────────
            GlassCard {
                width: parent.width

                Column {
                    width: parent.width
                    spacing: Theme.spacingSm

                    Text {
                        text: "API 설정"
                        font.pixelSize: Theme.fontSubtitle
                        font.weight: Font.DemiBold
                        color: Theme.textPrimary
                    }

                    // OpenRouter API 키
                    Row {
                        spacing: Theme.spacingSm
                        width: parent.width
                        Text {
                            text: "OpenRouter API 키"
                            font.pixelSize: Theme.fontBody
                            color: Theme.textSecondary
                            width: 160
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        TextField {
                            id: apiKeyField
                            width: parent.width - 180
                            echoMode: TextInput.Password
                            text: SettingsModel.apiKey
                            onTextChanged: SettingsModel.apiKey = text
                            placeholderText: "sk-or-v1-..."
                            color: Theme.textPrimary
                            font.pixelSize: Theme.fontBody
                            background: Rectangle {
                                radius: Theme.radiusSm
                                color: Theme.surfaceLight
                                border.color: apiKeyField.activeFocus ? Theme.accentNeon : Theme.glassBorder
                                border.width: 1
                            }
                        }
                    }

                    // Ollama URL
                    Row {
                        spacing: Theme.spacingSm
                        width: parent.width
                        Text {
                            text: "Ollama URL"
                            font.pixelSize: Theme.fontBody
                            color: Theme.textSecondary
                            width: 160
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        TextField {
                            id: ollamaField
                            width: parent.width - 180
                            text: SettingsModel.ollamaUrl
                            onTextChanged: SettingsModel.ollamaUrl = text
                            placeholderText: "http://localhost:11434"
                            color: Theme.textPrimary
                            font.pixelSize: Theme.fontBody
                            background: Rectangle {
                                radius: Theme.radiusSm
                                color: Theme.surfaceLight
                                border.color: ollamaField.activeFocus ? Theme.accentNeon : Theme.glassBorder
                                border.width: 1
                            }
                        }
                    }

                    Row {
                        layoutDirection: Qt.RightToLeft
                        width: parent.width
                        ActionButton {
                            text: "API 키 저장"
                            onClicked: SettingsModel.saveApiKey()
                        }
                    }
                }
            }

            // ── 데이터 경로 ─────────────────────────────
            GlassCard {
                width: parent.width

                Column {
                    width: parent.width
                    spacing: Theme.spacingSm

                    Text {
                        text: "데이터 경로"
                        font.pixelSize: Theme.fontSubtitle
                        font.weight: Font.DemiBold
                        color: Theme.textPrimary
                    }

                    Row {
                        spacing: Theme.spacingSm
                        width: parent.width
                        Text {
                            text: "미디어 루트"
                            font.pixelSize: Theme.fontBody
                            color: Theme.textSecondary
                            width: 160
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        TextField {
                            id: mediaField
                            width: parent.width - 220
                            text: SettingsModel.mediaRoot
                            onTextChanged: SettingsModel.mediaRoot = text
                            color: Theme.textPrimary
                            font.pixelSize: Theme.fontBody
                            background: Rectangle {
                                radius: Theme.radiusSm
                                color: Theme.surfaceLight
                                border.color: mediaField.activeFocus ? Theme.accentNeon : Theme.glassBorder
                                border.width: 1
                            }
                        }
                        ActionButton {
                            text: "..."
                            primary: false
                            onClicked: {
                                var p = SettingsModel.browseFolder();
                                if (p) { SettingsModel.mediaRoot = p; mediaField.text = p; }
                            }
                        }
                    }

                    Row {
                        layoutDirection: Qt.RightToLeft
                        width: parent.width
                        ActionButton {
                            text: "경로 저장"
                            onClicked: SettingsModel.savePaths()
                        }
                    }
                }
            }

            // ── 외관 ────────────────────────────────────
            GlassCard {
                width: parent.width

                Column {
                    width: parent.width
                    spacing: Theme.spacingSm

                    Text {
                        text: "외관"
                        font.pixelSize: Theme.fontSubtitle
                        font.weight: Font.DemiBold
                        color: Theme.textPrimary
                    }

                    Row {
                        spacing: Theme.spacingSm

                        Repeater {
                            model: ["Win11", "Light", "Dark"]

                            Rectangle {
                                width: 80; height: 36
                                radius: Theme.radiusSm
                                color: SettingsModel.themeMode === index ? Theme.primaryBlue : Theme.surfaceLight
                                border.color: SettingsModel.themeMode === index ? Theme.accentNeon : Theme.glassBorder
                                border.width: 1

                                Text {
                                    anchors.centerIn: parent
                                    text: modelData
                                    font.pixelSize: Theme.fontCaption
                                    font.weight: Font.DemiBold
                                    color: SettingsModel.themeMode === index ? (Theme.isDark ? "#0A0E1A" : "#FFFFFF") : Theme.textSecondary
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: SettingsModel.themeMode = index
                                }
                            }
                        }
                    }
                }
            }

            // ── STT 모델 ────────────────────────────────
            GlassCard {
                width: parent.width

                Column {
                    width: parent.width
                    spacing: Theme.spacingSm

                    Text {
                        text: "STT (음성 인식)"
                        font.pixelSize: Theme.fontSubtitle
                        font.weight: Font.DemiBold
                        color: Theme.textPrimary
                    }

                    Row {
                        spacing: Theme.spacingSm

                        Text {
                            text: "Whisper 모델"
                            font.pixelSize: Theme.fontBody
                            color: Theme.textSecondary
                            width: 160
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        ComboBox {
                            id: whisperCombo
                            model: ["large-v2", "large-v3", "medium", "small", "turbo"]
                            width: 200
                            currentIndex: {
                                var m = {"large-v2":0,"large-v3":1,"medium":2,"small":3,"turbo":4};
                                return m[SettingsModel.whisperModel] || 0;
                            }
                            onCurrentIndexChanged: {
                                var models = ["large-v2","large-v3","medium","small","turbo"];
                                SettingsModel.whisperModel = models[currentIndex];
                            }
                            background: Rectangle {
                                radius: Theme.radiusSm
                                color: Theme.surfaceLight
                                border.color: Theme.glassBorder
                                border.width: 1
                            }
                            contentItem: Text {
                                text: whisperCombo.displayText
                                font.pixelSize: Theme.fontCaption
                                color: Theme.textPrimary
                                verticalAlignment: Text.AlignVCenter
                                leftPadding: Theme.spacingSm
                            }
                        }
                    }
                }
            }

            // ── 번역 프로필 ─────────────────────────────
            GlassCard {
                width: parent.width

                Column {
                    width: parent.width
                    spacing: Theme.spacingSm

                    Text {
                        text: "한국어 번역"
                        font.pixelSize: Theme.fontSubtitle
                        font.weight: Font.DemiBold
                        color: Theme.textPrimary
                    }

                    Row {
                        spacing: Theme.spacingSm

                        Text {
                            text: "번역 프로필"
                            font.pixelSize: Theme.fontBody
                            color: Theme.textSecondary
                            width: 160
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        ComboBox {
                            id: profileCombo
                            model: ["DeepSeek V3.2", "GLM 5.1", "DeepSeek V3 Chat", "Gemma4 E4B (Local)", "Qwen 3.5 9B (Local)", "Qwen 3 14B (Local)", "Gemma 3 12B (Local)"]
                            width: 200
                            currentIndex: {
                                var m = {"default":0, "keeper":1, "deepseek_chat":2, "budget":3, "qwen35":4, "qwen3_14":5, "gemma3_12":6};
                                return m[SettingsModel.translationProfile] || 0;
                            }
                            onCurrentIndexChanged: {
                                var profiles = ["default", "keeper", "deepseek_chat", "budget", "qwen35", "qwen3_14", "gemma3_12"];
                                SettingsModel.translationProfile = profiles[currentIndex];
                            }
                            background: Rectangle {
                                radius: Theme.radiusSm
                                color: Theme.surfaceLight
                                border.color: Theme.glassBorder
                                border.width: 1
                            }
                            contentItem: Text {
                                text: profileCombo.displayText
                                font.pixelSize: Theme.fontCaption
                                color: Theme.textPrimary
                                verticalAlignment: Text.AlignVCenter
                                leftPadding: Theme.spacingSm
                            }
                        }
                    }

                    // ── [추가] 정밀 교정 LLM ──
                    Row {
                        spacing: Theme.spacingSm
                        Text {
                            text: "정밀 교정 LLM"
                            font.pixelSize: Theme.fontBody
                            color: Theme.textSecondary
                            width: 160
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        ComboBox {
                            id: correctionCombo
                            model: ["Qwen 3 235B (OpenRouter)", "DeepSeek V3.2 (OpenRouter)", "GLM 5.1 (OpenRouter)"]
                            width: 200
                            currentIndex: {
                                var m = {
                                    "qwen/qwen3-235b-a22b-2507": 0,
                                    "deepseek/deepseek-v3.2": 1,
                                    "z-ai/glm-5.1": 2
                                };
                                return m[SettingsModel.correctionProfile] !== undefined ? m[SettingsModel.correctionProfile] : 0;
                            }
                            onCurrentIndexChanged: {
                                var models = ["qwen/qwen3-235b-a22b-2507", "deepseek/deepseek-v3.2", "z-ai/glm-5.1"];
                                SettingsModel.correctionProfile = models[currentIndex];
                            }
                            background: Rectangle {
                                radius: Theme.radiusSm
                                color: Theme.surfaceLight
                                border.color: Theme.glassBorder
                                border.width: 1
                            }
                            contentItem: Text {
                                text: correctionCombo.displayText
                                font.pixelSize: Theme.fontCaption
                                color: Theme.textPrimary
                                verticalAlignment: Text.AlignVCenter
                                leftPadding: Theme.spacingSm
                            }
                        }
                    }
                }
            }

            // ── 기타 옵션 ───────────────────────────────
            GlassCard {
                width: parent.width

                Column {
                    width: parent.width
                    spacing: Theme.spacingSm

                    Text {
                        text: "기타 옵션"
                        font.pixelSize: Theme.fontSubtitle
                        font.weight: Font.DemiBold
                        color: Theme.textPrimary
                    }

                    Row {
                        spacing: Theme.spacingSm
                        Text {
                            text: "Harvest 동시 실행"
                            font.pixelSize: Theme.fontBody
                            color: Theme.textSecondary
                            width: 160
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        ComboBox {
                            id: harvestConcCombo
                            model: ["1", "2", "3", "4", "5"]
                            width: 120
                            currentIndex: Math.max(0, Math.min(4, (SettingsModel.harvestConcurrency || 2) - 1))
                            onCurrentIndexChanged: {
                                var vals = [1,2,3,4,5];
                                SettingsModel.harvestConcurrency = vals[currentIndex] || 2;
                            }
                            background: Rectangle {
                                radius: Theme.radiusSm
                                color: Theme.surfaceLight
                                border.color: Theme.glassBorder
                                border.width: 1
                            }
                            contentItem: Text {
                                text: harvestConcCombo.displayText
                                font.pixelSize: Theme.fontCaption
                                color: Theme.textPrimary
                                verticalAlignment: Text.AlignVCenter
                                leftPadding: Theme.spacingSm
                            }
                        }
                    }

                    Text {
                        text: "권장 2~3, 고성능 환경은 5 (OpenRouter 요청/DB 부하 증가)"
                        font.pixelSize: Theme.fontCaption
                        color: Theme.textMuted
                        leftPadding: 168
                    }

                    Row {
                        spacing: Theme.spacingSm
                        Text {
                            text: "Grok 스토리 맥락"
                            font.pixelSize: Theme.fontBody
                            color: Theme.textSecondary
                            width: 160
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Switch {
                            id: grokSwitch
                            checked: SettingsModel.grokEnabled
                            onToggled: SettingsModel.grokEnabled = checked
                            
                            indicator: Rectangle {
                                implicitWidth: 40
                                implicitHeight: 20
                                x: grokSwitch.leftPadding
                                y: parent.height / 2 - height / 2
                                radius: 10
                                color: grokSwitch.checked ? Theme.accentNeon : Theme.surfaceLight
                                border.color: grokSwitch.checked ? Theme.accentNeon : Theme.glassBorder
                                border.width: 1

                                Rectangle {
                                    x: grokSwitch.checked ? parent.width - width - 2 : 2
                                    y: 2
                                    width: 16
                                    height: 16
                                    radius: 8
                                    color: "white"
                                    Behavior on x { NumberAnimation { duration: 150 } }
                                }
                            }
                        }
                    }

                    Text {
                        text: "Harvest 후 Grok API로 스토리 컨텍스트 캐시 생성"
                        font.pixelSize: Theme.fontCaption
                        color: Theme.textMuted
                        leftPadding: 168
                    }

                    Rectangle {
                        width: parent.width; height: 1
                        color: Theme.glassBorder
                    }

                    Row {
                        spacing: Theme.spacingSm
                        Text {
                            text: "DPI 우회 (GoodbyeDPI)"
                            font.pixelSize: Theme.fontBody
                            color: Theme.textSecondary
                            width: 160
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Switch {
                            id: dpiSwitch
                            checked: SettingsModel.dpiBypass
                            onToggled: SettingsModel.dpiBypass = checked

                            indicator: Rectangle {
                                implicitWidth: 40
                                implicitHeight: 20
                                x: dpiSwitch.leftPadding
                                y: parent.height / 2 - height / 2
                                radius: 10
                                color: dpiSwitch.checked ? Theme.accentNeon : Theme.surfaceLight
                                border.color: dpiSwitch.checked ? Theme.accentNeon : Theme.glassBorder
                                border.width: 1

                                Rectangle {
                                    x: dpiSwitch.checked ? parent.width - width - 2 : 2
                                    y: 2
                                    width: 16
                                    height: 16
                                    radius: 8
                                    color: "white"
                                    Behavior on x { NumberAnimation { duration: 150 } }
                                }
                            }
                        }
                    }

                    Text {
                        text: "크롤링 시 SNI 차단 우회 (tools/goodbyedpi 필요)"
                        font.pixelSize: Theme.fontCaption
                        color: Theme.textMuted
                        leftPadding: 168
                    }

                    Row {
                        layoutDirection: Qt.RightToLeft
                        width: parent.width
                        ActionButton {
                            text: "옵션 저장"
                            onClicked: SettingsModel.saveOptions()
                        }
                    }
                }
            }

            // ── 버전 정보 ───────────────────────────────
            Text {
                text: "JAVSTORY Pro v3.0 — PySide6 + QML"
                font.pixelSize: Theme.fontCaption
                color: Theme.textMuted
                anchors.horizontalCenter: parent.horizontalCenter
            }

            Item { height: Theme.spacingLg }
        }
    }
}
