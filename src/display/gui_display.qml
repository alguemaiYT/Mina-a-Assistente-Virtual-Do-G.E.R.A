import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtGraphicalEffects 1.15

Rectangle {
    id: root
    color: lc ? lc.get("root", "color") : "#f5f5f5"

    // Helper: read a layout value with a fallback
    function l(section, key, fallback) {
        if (!lc) return fallback
        var v = lc.get(section, key)
        return (v !== undefined && v !== null) ? v : fallback
    }

    // 信号定义 - 与 Python 回调对接
    signal autoButtonClicked()
    signal abortButtonClicked()
    signal sendButtonClicked(string text)
    // 标题栏相关信号
    signal titleMinimize()
    signal titleClose()
    signal titleDragStart(real mouseX, real mouseY)
    signal titleDragMoveTo(real mouseX, real mouseY)
    signal titleDragEnd()

    // 主布局
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 0
        spacing: 0

        // 自定义标题栏：最小化、关闭、可拖动
        Rectangle {
            id: titleBar
            Layout.fillWidth: true
            Layout.preferredHeight: l("titleBar", "height", 36)
            color: l("titleBar", "color", "#f7f8fa")
            border.width: 0

            // 整条标题栏拖动（使用屏幕坐标，避免累计误差导致抖动）
            // 放在最底层，让按钮的 MouseArea 可以优先响应
            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.LeftButton
                onPressed: {
                    root.titleDragStart(mouse.x, mouse.y)
                }
                onPositionChanged: {
                    if (pressed) {
                        root.titleDragMoveTo(mouse.x, mouse.y)
                    }
                }
                onReleased: {
                    root.titleDragEnd()
                }
                z: 0  // 最底层
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 8
                spacing: 8
                z: 1  // 按钮层在拖动层上方

                // Status indicator + text in title bar
                RowLayout {
                    Layout.fillWidth: false
                    spacing: 6

                    Rectangle {
                        id: statusDot
                        width: l("statusDot", "width", 8)
                        height: l("statusDot", "height", 8)
                        radius: l("statusDot", "radius", 4)
                        color: {
                            var st = displayModel ? displayModel.statusText : ""
                            if (st.indexOf("Ready") !== -1 || st.indexOf("GUI Ready") !== -1) return l("statusDot", "colorReady", "#00b42a")
                            if (st.indexOf("Listening") !== -1 || st.indexOf("hearing") !== -1) return l("statusDot", "colorListening", "#ff7d00")
                            if (st.indexOf("Thinking") !== -1 || st.indexOf("Transcribing") !== -1) return l("statusDot", "colorThinking", "#165dff")
                            if (st.indexOf("error") !== -1 || st.indexOf("fail") !== -1 || st.indexOf("unavailable") !== -1) return l("statusDot", "colorError", "#f53f3f")
                            return l("statusDot", "colorDefault", "#c9cdd4")
                        }
                        Behavior on color { ColorAnimation { duration: 300; easing.type: Easing.OutCubic } }
                    }

                    Text {
                        text: displayModel ? displayModel.statusText : ""
                        font.family: "PingFang SC, Microsoft YaHei UI"
                        font.pixelSize: l("statusText", "fontSize", 11)
                        color: l("statusText", "color", "#86909c")
                        elide: Text.ElideRight
                        Layout.maximumWidth: l("statusText", "maxWidth", 200)
                    }
                }

                // 左侧拖动区域
                Item { id: dragArea; Layout.fillWidth: true; Layout.fillHeight: true }

                // 最小化
                Rectangle {
                    id: btnMin
                    width: l("btnMin", "width", 24); height: l("btnMin", "height", 24); radius: l("btnMin", "radius", 6)
                    color: btnMinMouse.pressed ? l("btnMin", "colorPressed", "#e5e6eb") : (btnMinMouse.containsMouse ? l("btnMin", "colorHover", "#f2f3f5") : l("btnMin", "colorNormal", "transparent"))
                    z: 2  // 确保按钮在最上层
                    Behavior on color { ColorAnimation { duration: 150; easing.type: Easing.OutCubic } }
                    Text { anchors.centerIn: parent; text: "–"; font.pixelSize: l("btnMin", "iconSize", 14); color: l("btnMin", "iconColor", "#4e5969") }
                    MouseArea {
                        id: btnMinMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: root.titleMinimize()
                    }
                }

                // 关闭
                Rectangle {
                    id: btnClose
                    width: l("btnClose", "width", 24); height: l("btnClose", "height", 24); radius: l("btnClose", "radius", 6)
                    color: btnCloseMouse.pressed ? l("btnClose", "colorPressed", "#f53f3f") : (btnCloseMouse.containsMouse ? l("btnClose", "colorHover", "#ff7875") : l("btnClose", "colorNormal", "transparent"))
                    z: 2  // 确保按钮在最上层
                    Behavior on color { ColorAnimation { duration: 150; easing.type: Easing.OutCubic } }
                    Text { anchors.centerIn: parent; text: "×"; font.pixelSize: l("btnClose", "iconSize", 14); color: btnCloseMouse.containsMouse ? l("btnClose", "iconColorHover", "white") : l("btnClose", "iconColor", "#86909c") }
                    MouseArea {
                        id: btnCloseMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: root.titleClose()
                    }
                }
            }
        }

        // 内容区域（表情、TTS, 输入）
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: l("contentArea", "margins", 12)
            spacing: l("contentArea", "spacing", 12)

            // 表情显示区域
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: l("emotionArea", "minimumHeight", 80)

                // Smooth fade transition on emotion change
                Rectangle {
                    id: emotionContainer
                    anchors.centerIn: parent
                    width: emotionLoader.maxSize
                    height: emotionLoader.maxSize
                    color: "transparent"

                    // Subtle glow effect behind emotion during active states
                    Rectangle {
                        id: emotionGlow
                        anchors.centerIn: parent
                        width: parent.width * l("emotionGlow", "scaleFactor", 1.2)
                        height: parent.height * l("emotionGlow", "scaleFactor", 1.2)
                        radius: width / 2
                        color: "transparent"
                        border.width: 0
                        visible: glowAnimation.running

                        property bool isActive: {
                            var st = displayModel ? displayModel.statusText : ""
                            return st.indexOf("Listening") !== -1 || st.indexOf("hearing") !== -1
                        }

                        RadialGradient {
                            anchors.fill: parent
                            gradient: Gradient {
                                GradientStop { position: 0.0; color: l("emotionGlow", "colorInner", "#20165dff") }
                                GradientStop { position: 1.0; color: l("emotionGlow", "colorOuter", "transparent") }
                            }
                        }

                        SequentialAnimation on opacity {
                            id: glowAnimation
                            running: emotionGlow.isActive
                            loops: Animation.Infinite
                            NumberAnimation { from: 0.3; to: 1.0; duration: 1000; easing.type: Easing.InOutSine }
                            NumberAnimation { from: 1.0; to: 0.3; duration: 1000; easing.type: Easing.InOutSine }
                        }
                    }

                    Loader {
                        id: emotionLoader
                        anchors.centerIn: parent
                        // Reference the Item ancestor (emotion display area) for sizing
                        property real maxSize: Math.max(Math.min(emotionContainer.parent.width, emotionContainer.parent.height) * l("emotionArea", "sizeFactor", 0.7), l("emotionArea", "minSize", 60))
                        width: maxSize
                        height: maxSize

                        // Smooth opacity transition when emotion changes
                        opacity: 1.0
                        Behavior on opacity { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }

                        sourceComponent: {
                            var path = displayModel ? displayModel.emotionPath : ""
                            if (!path || path.length === 0) {
                                return emojiComponent
                            }
                            if (path.indexOf(".gif") !== -1) {
                                return gifComponent
                            }
                            if (path.indexOf(".") !== -1) {
                                return imageComponent
                            }
                            return emojiComponent
                        }

                        Component {
                            id: gifComponent
                            AnimatedImage {
                                anchors.fill: parent
                                width: parent.width
                                height: parent.height
                                fillMode: Image.PreserveAspectCrop
                                source: displayModel ? displayModel.emotionPath : ""
                                playing: true
                                speed: 1.05
                                cache: true
                                clip: true
                                asynchronous: true
                                onStatusChanged: {
                                    if (status === Image.Error) {
                                        console.error("AnimatedImage error:", errorString, "src=", source)
                                    }
                                }
                            }
                        }

                        Component {
                            id: imageComponent
                            Image {
                                anchors.fill: parent
                                width: parent.width
                                height: parent.height
                                fillMode: Image.PreserveAspectCrop
                                source: displayModel ? displayModel.emotionPath : ""
                                cache: true
                                clip: true
                                asynchronous: true
                                onStatusChanged: {
                                    if (status === Image.Error) {
                                        console.error("Image error:", errorString, "src=", source)
                                    }
                                }
                            }
                        }

                        Component {
                            id: emojiComponent
                            Text {
                                text: displayModel ? displayModel.emotionPath : "😊"
                                width: parent.width
                                height: parent.height
                                font.pixelSize: Math.max(Math.min(parent.width, parent.height) * 0.8, l("emotionArea", "minSize", 60))
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                                anchors.fill: parent
                            }
                        }
                    }
                }
            }

            // TTS 文本显示区域
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: l("ttsArea", "height", 60)
                color: l("ttsArea", "color", "transparent")

                Text {
                    id: ttsTextDisplay
                    anchors.fill: parent
                    anchors.margins: l("ttsArea", "textMargins", 10)
                    text: displayModel ? displayModel.ttsText : ""
                    font.family: "PingFang SC, Microsoft YaHei UI"
                    font.pixelSize: l("ttsArea", "fontSize", 13)
                    color: l("ttsArea", "textColor", "#555555")
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    wrapMode: Text.WordWrap
                }

                // Smooth fade animation when TTS text changes
                Connections {
                    target: displayModel
                    function onTtsTextChanged() {
                        ttsTextFade.restart()
                    }
                }

                SequentialAnimation {
                    id: ttsTextFade
                    NumberAnimation { target: ttsTextDisplay; property: "opacity"; to: 0.4; duration: 80 }
                    NumberAnimation { target: ttsTextDisplay; property: "opacity"; to: 1.0; duration: 200; easing.type: Easing.OutCubic }
                }
            }
        }

        // 按钮区域（统一配色与尺寸）
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: l("buttonBar", "height", 72)
            color: l("buttonBar", "color", "#f7f8fa")

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: l("buttonBar", "margins", 12)
                anchors.rightMargin: l("buttonBar", "margins", 12)
                anchors.bottomMargin: l("buttonBar", "bottomMargin", 10)
                spacing: l("buttonBar", "spacing", 6)

                // 自动模式按钮 - 主色
                Button {
                    id: autoBtn
                    Layout.preferredWidth: l("autoButton", "preferredWidth", 100)
                    Layout.fillWidth: true
                    Layout.maximumWidth: l("autoButton", "maxWidth", 140)
                    Layout.preferredHeight: l("autoButton", "height", 38)
                    text: displayModel ? displayModel.buttonText : "Start Conversation"
                    visible: true

                    background: Rectangle {
                        color: autoBtn.pressed ? l("autoButton", "colorPressed", "#0e42d2") : (autoBtn.hovered ? l("autoButton", "colorHover", "#4080ff") : l("autoButton", "colorNormal", "#165dff"))
                        radius: l("autoButton", "radius", 8)
                        Behavior on color { ColorAnimation { duration: 120; easing.type: Easing.OutCubic } }

                        scale: autoBtn.pressed ? 0.96 : 1.0
                        Behavior on scale { NumberAnimation { duration: 100; easing.type: Easing.OutCubic } }
                    }

                    contentItem: Text {
                        text: autoBtn.text
                        font.family: "PingFang SC, Microsoft YaHei UI"
                        font.pixelSize: l("autoButton", "fontSize", 12)
                        color: l("autoButton", "textColor", "white")
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                    onClicked: root.autoButtonClicked()
                }

                // 打断对话 - 次要色
                Button {
                    id: abortBtn
                    Layout.preferredWidth: l("abortButton", "preferredWidth", 80)
                    Layout.fillWidth: true
                    Layout.maximumWidth: l("abortButton", "maxWidth", 120)
                    Layout.preferredHeight: l("abortButton", "height", 38)
                    text: "Interrupt"

                    background: Rectangle {
                        color: abortBtn.pressed ? l("abortButton", "colorPressed", "#e5e6eb") : (abortBtn.hovered ? l("abortButton", "colorHover", "#f2f3f5") : l("abortButton", "colorNormal", "#eceff3"))
                        radius: l("abortButton", "radius", 8)
                        Behavior on color { ColorAnimation { duration: 120; easing.type: Easing.OutCubic } }

                        scale: abortBtn.pressed ? 0.96 : 1.0
                        Behavior on scale { NumberAnimation { duration: 100; easing.type: Easing.OutCubic } }
                    }
                    contentItem: Text {
                        text: abortBtn.text
                        font.family: "PingFang SC, Microsoft YaHei UI"
                        font.pixelSize: l("abortButton", "fontSize", 12)
                        color: l("abortButton", "textColor", "#1d2129")
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                    onClicked: root.abortButtonClicked()
                }

                // 输入 + 发送
                RowLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 120
                    Layout.preferredHeight: l("textInput", "height", 38)
                    spacing: l("buttonBar", "spacing", 6)

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: l("textInput", "height", 38)
                        color: l("textInput", "bgColor", "white")
                        radius: l("textInput", "radius", 8)
                        border.color: textInput.activeFocus ? l("textInput", "borderColorFocused", "#165dff") : l("textInput", "borderColorNormal", "#e5e6eb")
                        border.width: textInput.activeFocus ? l("textInput", "borderWidthFocused", 2) : l("textInput", "borderWidthNormal", 1)
                        Behavior on border.color { ColorAnimation { duration: 200; easing.type: Easing.OutCubic } }
                        Behavior on border.width { NumberAnimation { duration: 150; easing.type: Easing.OutCubic } }

                        TextInput {
                            id: textInput
                            anchors.fill: parent
                            anchors.leftMargin: l("textInput", "leftMargin", 10)
                            anchors.rightMargin: l("textInput", "rightMargin", 10)
                            verticalAlignment: TextInput.AlignVCenter
                            font.family: "PingFang SC, Microsoft YaHei UI"
                            font.pixelSize: l("textInput", "fontSize", 12)
                            color: l("textInput", "textColor", "#333333")
                            selectByMouse: true
                            clip: true

                            // 占位符 - visible when empty (even when focused)
                            Text {
                                anchors.fill: parent
                                text: "Type a message..."
                                font: textInput.font
                                color: l("textInput", "placeholderColor", "#c9cdd4")
                                verticalAlignment: Text.AlignVCenter
                                visible: !textInput.text
                                opacity: textInput.activeFocus ? 0.6 : 1.0
                                Behavior on opacity { NumberAnimation { duration: 200 } }
                            }

                            Keys.onReturnPressed: { if (textInput.text.trim().length > 0) { root.sendButtonClicked(textInput.text); textInput.text = "" } }
                        }
                    }

                    Button {
                        id: sendBtn
                        Layout.preferredWidth: l("sendButton", "preferredWidth", 60)
                        Layout.maximumWidth: l("sendButton", "maxWidth", 84)
                        Layout.preferredHeight: l("sendButton", "height", 38)
                        text: "Send"
                        enabled: textInput.text.trim().length > 0
                        background: Rectangle {
                            color: !sendBtn.enabled ? l("sendButton", "colorDisabled", "#a0bfff") : (sendBtn.pressed ? l("sendButton", "colorPressed", "#0e42d2") : (sendBtn.hovered ? l("sendButton", "colorHover", "#4080ff") : l("sendButton", "colorNormal", "#165dff")))
                            radius: l("sendButton", "radius", 8)
                            Behavior on color { ColorAnimation { duration: 120; easing.type: Easing.OutCubic } }

                            scale: sendBtn.pressed ? 0.96 : 1.0
                            Behavior on scale { NumberAnimation { duration: 100; easing.type: Easing.OutCubic } }
                        }
                        contentItem: Text {
                            text: sendBtn.text
                            font.family: "PingFang SC, Microsoft YaHei UI"
                            font.pixelSize: l("sendButton", "fontSize", 12)
                            color: l("sendButton", "textColor", "white")
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            opacity: sendBtn.enabled ? 1.0 : 0.7
                        }
                        onClicked: { if (textInput.text.trim().length > 0) { root.sendButtonClicked(textInput.text); textInput.text = "" } }
                    }
                }

            }
        }
    }

    // =========================================================================
    // STUDIO / LAYOUT EDITOR OVERLAY
    // =========================================================================
    // Visible only when lc.studioMode === true (-s flag).
    // A floating panel lets the user pick any section/key and edit its value.
    // Changes are persisted immediately to config/layout_config.json.
    // =========================================================================

    Rectangle {
        id: studioOverlay
        visible: lc ? lc.studioMode : false
        anchors.fill: parent
        color: "transparent"
        z: 1000

        // Highlight borders on major areas so the user can see what is editable
        Rectangle {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: l("titleBar", "height", 36)
            color: "transparent"
            border.color: "#ff4444"
            border.width: 1
            visible: studioOverlay.visible
            MouseArea {
                anchors.fill: parent
                onClicked: { sectionCombo.currentIndex = sectionCombo.find("titleBar") }
                propagateComposedEvents: true
            }
            Text { anchors.centerIn: parent; text: "titleBar"; color: "#ff4444"; font.pixelSize: 9; opacity: 0.8 }
        }

        // Side panel for editing properties
        Rectangle {
            id: studioPanel
            width: 280
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.right: parent.right
            color: "#f0f0f0"
            border.color: "#ccc"
            border.width: 1
            z: 1001

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 6

                // Header
                Text {
                    text: "🎨 Layout Editor"
                    font.pixelSize: 14
                    font.bold: true
                    color: "#333"
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                }

                Rectangle { Layout.fillWidth: true; height: 1; color: "#ddd" }

                // Section selector
                Text { text: "Section:"; font.pixelSize: 11; color: "#666" }
                ComboBox {
                    id: sectionCombo
                    Layout.fillWidth: true
                    model: lc ? lc.allSections() : []
                    onCurrentTextChanged: {
                        if (lc && currentText) {
                            keyCombo.model = lc.sectionKeys(currentText)
                            keyCombo.currentIndex = 0
                        }
                    }
                    Component.onCompleted: {
                        if (lc) {
                            model = lc.allSections()
                            if (model.length > 0) {
                                currentIndex = 0
                                keyCombo.model = lc.sectionKeys(model[0])
                            }
                        }
                    }
                }

                // Key selector
                Text { text: "Property:"; font.pixelSize: 11; color: "#666" }
                ComboBox {
                    id: keyCombo
                    Layout.fillWidth: true
                    model: []
                    onCurrentTextChanged: {
                        if (lc && sectionCombo.currentText && currentText) {
                            var val = lc.get(sectionCombo.currentText, currentText)
                            valueField.text = (val !== undefined && val !== null) ? String(val) : ""
                        }
                    }
                }

                // Current value display
                Text { text: "Value:"; font.pixelSize: 11; color: "#666" }
                Rectangle {
                    Layout.fillWidth: true
                    height: 32
                    color: "white"
                    border.color: valueField.activeFocus ? "#165dff" : "#ccc"
                    border.width: 1
                    radius: 4

                    TextInput {
                        id: valueField
                        anchors.fill: parent
                        anchors.margins: 6
                        verticalAlignment: TextInput.AlignVCenter
                        font.pixelSize: 12
                        color: "#333"
                        selectByMouse: true
                        clip: true

                        Keys.onReturnPressed: applyBtn.clicked()
                    }
                }

                // Color preview (shown when value looks like a color)
                Rectangle {
                    Layout.fillWidth: true
                    height: 24
                    radius: 4
                    color: {
                        var v = valueField.text.toLowerCase()
                        if (v && (v.charAt(0) === '#' || v.indexOf("rgb") === 0)) return v
                        return "transparent"
                    }
                    border.color: "#ccc"
                    border.width: 1
                    visible: {
                        var v = valueField.text.toLowerCase()
                        return v && (v.charAt(0) === '#' || v.indexOf("rgb") === 0)
                    }
                }

                // Apply button
                Button {
                    id: applyBtn
                    Layout.fillWidth: true
                    text: "Apply"
                    onClicked: {
                        if (lc && sectionCombo.currentText && keyCombo.currentText) {
                            var raw = valueField.text
                            var key = keyCombo.currentText.toLowerCase()
                            var isColor = key.indexOf("color") !== -1
                            var val
                            if (isColor) {
                                val = raw
                            } else {
                                var num = Number(raw)
                                val = isNaN(num) ? raw : num
                            }
                            lc.set(sectionCombo.currentText, keyCombo.currentText, val)
                        }
                    }
                    background: Rectangle {
                        color: applyBtn.pressed ? "#0e42d2" : (applyBtn.hovered ? "#4080ff" : "#165dff")
                        radius: 6
                    }
                    contentItem: Text {
                        text: applyBtn.text; color: "white"; font.pixelSize: 12
                        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                    }
                }

                Rectangle { Layout.fillWidth: true; height: 1; color: "#ddd" }

                // Reset section
                Button {
                    id: resetSectionBtn
                    Layout.fillWidth: true
                    text: "Reset Section"
                    onClicked: {
                        if (lc && sectionCombo.currentText) {
                            lc.resetSection(sectionCombo.currentText)
                            // refresh displayed value
                            if (keyCombo.currentText) {
                                var val = lc.get(sectionCombo.currentText, keyCombo.currentText)
                                valueField.text = (val !== undefined && val !== null) ? String(val) : ""
                            }
                        }
                    }
                    background: Rectangle {
                        color: resetSectionBtn.pressed ? "#e5e6eb" : (resetSectionBtn.hovered ? "#f2f3f5" : "#eceff3")
                        radius: 6
                    }
                    contentItem: Text {
                        text: resetSectionBtn.text; color: "#333"; font.pixelSize: 11
                        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                    }
                }

                // Reset all
                Button {
                    id: resetAllBtn
                    Layout.fillWidth: true
                    text: "Reset All to Defaults"
                    onClicked: {
                        if (lc) {
                            lc.resetAll()
                            if (sectionCombo.currentText && keyCombo.currentText) {
                                var val = lc.get(sectionCombo.currentText, keyCombo.currentText)
                                valueField.text = (val !== undefined && val !== null) ? String(val) : ""
                            }
                        }
                    }
                    background: Rectangle {
                        color: resetAllBtn.pressed ? "#f53f3f" : (resetAllBtn.hovered ? "#ff7875" : "#ff4d4f")
                        radius: 6
                    }
                    contentItem: Text {
                        text: resetAllBtn.text; color: "white"; font.pixelSize: 11
                        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                    }
                }

                // Spacer
                Item { Layout.fillHeight: true }

                // Info
                Text {
                    text: "Changes are saved automatically.\nRestart to see full effect of\nsome layout changes."
                    font.pixelSize: 9
                    color: "#999"
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                }
            }
        }
    }
}
