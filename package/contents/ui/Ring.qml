import QtQuick

// Circular gauge: a gradient arc from 12 o'clock, plus an optional pace tick
// showing where usage would be if it were spent evenly across the window.
Canvas {
    id: ring

    property real value: 0
    property real pace: -1
    property real thickness: 10
    property color colorA: "#22d3ee"
    property color colorB: "#34d399"
    property color trackColor: "#30808080"
    property color paceColor: "#ffffff"
    property real glow: 0
    property bool animated: true

    property real shown: 0
    Behavior on shown {
        enabled: ring.animated
        NumberAnimation { duration: 1100; easing.type: Easing.OutCubic }
    }

    function lerp(t) {
        return Qt.rgba(colorA.r + (colorB.r - colorA.r) * t,
                       colorA.g + (colorB.g - colorA.g) * t,
                       colorA.b + (colorB.b - colorA.b) * t, 1)
    }

    onValueChanged: shown = Math.max(0, Math.min(100, value))
    Component.onCompleted: shown = Math.max(0, Math.min(100, value))
    onShownChanged: requestPaint()
    onPaceChanged: requestPaint()
    onColorAChanged: requestPaint()
    onColorBChanged: requestPaint()
    onTrackColorChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()

    onPaint: {
        var ctx = getContext("2d")
        ctx.reset()
        var cx = width / 2, cy = height / 2
        var r = Math.min(width, height) / 2 - thickness / 2 - glow
        var start = -Math.PI / 2
        var sweep = 2 * Math.PI * shown / 100
        ctx.lineWidth = thickness
        ctx.lineCap = "butt"

        ctx.strokeStyle = trackColor
        ctx.beginPath()
        ctx.arc(cx, cy, r, 0, 2 * Math.PI)
        ctx.stroke()

        if (shown > 0.05) {
            ctx.lineCap = "round"
            if (glow > 0) {
                ctx.save()
                ctx.shadowColor = colorB
                ctx.shadowBlur = glow
                ctx.strokeStyle = colorB
                ctx.beginPath()
                ctx.arc(cx, cy, r, start, start + sweep)
                ctx.stroke()
                ctx.restore()
            }
            // Short overlapping segments give a gradient along the arc.
            var steps = sweep < 0.3 ? 1 : Math.ceil(sweep / 0.06)
            for (var i = 0; i < steps; i++) {
                if (i > 0 && i < steps - 1)
                    ctx.lineCap = "butt"
                else
                    ctx.lineCap = "round"
                ctx.strokeStyle = lerp(steps > 1 ? i / (steps - 1) : 1)
                ctx.beginPath()
                ctx.arc(cx, cy, r, start + sweep * i / steps, start + sweep * Math.min(1, (i + 1.3) / steps))
                ctx.stroke()
            }
        }

        if (pace >= 0) {
            var a = start + 2 * Math.PI * Math.min(100, pace) / 100
            var extra = Math.max(1.5, thickness * 0.28)
            ctx.lineCap = "round"
            ctx.lineWidth = Math.max(1.5, thickness * 0.24)
            ctx.strokeStyle = paceColor
            ctx.beginPath()
            ctx.moveTo(cx + Math.cos(a) * (r - thickness / 2 - extra), cy + Math.sin(a) * (r - thickness / 2 - extra))
            ctx.lineTo(cx + Math.cos(a) * (r + thickness / 2 + extra), cy + Math.sin(a) * (r + thickness / 2 + extra))
            ctx.stroke()
        }
    }
}
