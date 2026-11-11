import QtQuick

// Usage day by day: session as a filled saw-tooth, the week as a line, days marked.
Canvas {
    id: chart

    property var history: []
    property real now: Date.now() / 1000
    property real span: 7 * 86400
    property color gridColor: "#30808080"
    property color sessionColor: "#22d3ee"
    property color weekColor: "#a78bfa"

    onHistoryChanged: requestPaint()
    onNowChanged: requestPaint()
    onGridColorChanged: requestPaint()
    onSessionColorChanged: requestPaint()
    onWeekColorChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()

    function px(t) { return (t - (now - span)) / span * width }
    function py(v) { return 2 + (height - 4) * (1 - v / 100) }

    // A falling value means the window was reset: keep the drop vertical.
    function trace(ctx, rows, col) {
        var started = false, prev = null
        for (var i = 0; i < rows.length; i++) {
            var v = rows[i][col]
            if (v === null || v === undefined) continue
            if (!started) { ctx.moveTo(px(rows[i][0]), py(v)); started = true }
            else {
                if (v < prev) ctx.lineTo(px(rows[i][0]), py(prev))
                ctx.lineTo(px(rows[i][0]), py(v))
            }
            prev = v
        }
        return prev
    }

    onPaint: {
        var ctx = getContext("2d")
        ctx.reset()
        ctx.lineWidth = 1
        ctx.strokeStyle = gridColor
        ;[0, 50, 100].forEach(function (v) {
            ctx.beginPath()
            ctx.moveTo(0, py(v))
            ctx.lineTo(width, py(v))
            ctx.stroke()
        })
        var midnight = new Date(now * 1000)
        midnight.setHours(0, 0, 0, 0)
        for (var d = 0; d < 7; d++) {
            var at = new Date(midnight.getFullYear(), midnight.getMonth(), midnight.getDate() - d).getTime() / 1000
            ctx.beginPath()
            ctx.moveTo(px(at), 0)
            ctx.lineTo(px(at), height)
            ctx.stroke()
        }

        var rows = (history || []).filter(function (r) { return r[0] >= now - span })
        if (rows.length < 2) return

        var session = rows.filter(function (r) { return r[1] !== null && r[1] !== undefined })
        if (session.length > 1) {
            var fill = ctx.createLinearGradient(0, 0, 0, height)
            fill.addColorStop(0, Qt.rgba(sessionColor.r, sessionColor.g, sessionColor.b, 0.42))
            fill.addColorStop(1, Qt.rgba(sessionColor.r, sessionColor.g, sessionColor.b, 0.02))
            ctx.fillStyle = fill
            ctx.beginPath()
            trace(ctx, session, 1)
            ctx.lineTo(px(session[session.length - 1][0]), py(0))
            ctx.lineTo(px(session[0][0]), py(0))
            ctx.closePath()
            ctx.fill()

            ctx.lineJoin = "round"
            ctx.lineWidth = 1.75
            ctx.strokeStyle = sessionColor
            ctx.beginPath()
            trace(ctx, session, 1)
            ctx.stroke()
        }

        ctx.lineWidth = 1.75
        ctx.strokeStyle = weekColor
        ctx.beginPath()
        trace(ctx, rows, 2)
        ctx.stroke()
    }
}
