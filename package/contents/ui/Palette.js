.pragma library

var override_ = "auto"

var ru = {
    "d": "д", "h": "ч", "min": "мин", "now": "сейчас",
    "just now": "только что", "%1 ago": "%1 назад", "tomorrow %1": "завтра %1",
    "used": "использовано", "%1% left": "осталось %1%", "resets in %1": "сброс через %1",
    "Session": "Сессия", "Week": "Неделя", "5-hour window": "окно 5 часов", "7-day window": "окно 7 дней",
    "No data": "Нет данных", "Waiting for the first answer from Claude Code": "Жду первого ответа от Claude Code",
    "Limit reached": "Лимит исчерпан", "Using it faster than the pace": "Расход выше темпа",
    "Enough, but tight": "Запаса хватает, но впритык", "All clear": "Можно работать спокойно",
    "Windows just started, forecast comes later": "Окна только начались, прогноз позже",
    "Session limit reached": "Сессия исчерпана", "Week limit reached": "Неделя исчерпана",
    "%1, resets in %2": "%1, сброс через %2",
    "Session: at this pace it runs out at %1, %2 before the reset": "Сессия: при таком темпе лимит кончится в %1, за %2 до сброса",
    "Week: at this pace it runs out at %1, %2 before the reset": "Неделя: при таком темпе лимит кончится в %1, за %2 до сброса",
    "Session: about %1% of the limit by the reset": "Сессия: к сбросу выйдет примерно %1% лимита",
    "Week: about %1% of the limit by the reset": "Неделя: к сбросу выйдет примерно %1% лимита",
    "Tick on the ring: usage if spent evenly": "Риска на кольце: столько ушло бы при ровном расходе",
    "Week, %1": "Неделя, %1", "%1%, %2% left": "%1%, осталось %2%",
    "Last 24 hours": "За 24 часа", "session": "сессия", "week": "неделя",
    "The chart fills in after a few updates": "График наберётся за пару обновлений",
    "24 h": "24 ч", "7 days": "7 дней",
    "Could not update: %1": "Не удалось обновить: %1", "Showing the last known data": "Показаны последние данные",
    "%1: %2% used, %3% left": "%1: использовано %2%, осталось %3%", "The data collector did not answer": "Сборщик данных не ответил",
    "may hit the limit": "риск упереться в лимит",
    "claude not found": "не найден claude",
    "General": "Общие", "Panel icon:": "Значок на панели:", "Show numbers next to the rings": "Показывать цифры рядом с кольцами"
}

function setLanguage(value) { override_ = value || "auto" }

function isRussian() {
    return override_ === "auto" ? Qt.locale().name.indexOf("ru") === 0 : override_ === "ru"
}

function t(source) {
    var text = (isRussian() && ru[source]) || source
    for (var i = 1; i < arguments.length; i++)
        text = text.replace("%" + i, arguments[i])
    return text
}

// Each window keeps its own colour so the rings can't be mixed up: blue for
// the session, violet for the week. Only a nearly spent limit turns red.
function level(pct, kind) {
    if (pct >= 85) return { a: "#fb923c", b: "#ef4444" }
    if (kind === "week") return { a: "#a78bfa", b: "#d946ef" }
    return { a: "#22d3ee", b: "#3b82f6" }
}

function duration(seconds) {
    if (seconds <= 0) return t("now")
    var m = Math.ceil(seconds / 60)
    var d = Math.floor(m / 1440)
    var h = Math.floor((m % 1440) / 60)
    m = m % 60
    if (d > 0) return d + " " + t("d") + " " + h + " " + t("h")
    if (h > 0) return h + " " + t("h") + " " + m + " " + t("min")
    return m + " " + t("min")
}

function clock(epoch, now) {
    var when = new Date(epoch * 1000)
    var n = new Date(now * 1000)
    var locale = override_ === "auto" ? Qt.locale() : Qt.locale(override_ === "ru" ? "ru_RU" : "en_US")
    var hhmm = when.toLocaleTimeString(locale, 1)
    if (when.toDateString() === n.toDateString()) return hhmm
    var tomorrow = new Date(n.getFullYear(), n.getMonth(), n.getDate() + 1)
    if (when.toDateString() === tomorrow.toDateString()) return t("tomorrow %1", hhmm)
    return locale.dayName(when.getDay(), 1) + " " + hhmm
}

function ago(seconds) {
    if (seconds < 60) return t("just now")
    return t("%1 ago", duration(seconds))
}

function requests(n) {
    var a = Math.abs(n) % 100, b = a % 10
    if (!isRussian()) return n === 1 ? "request" : "requests"
    if (a > 10 && a < 20) return "запросов"
    if (b > 1 && b < 5) return "запроса"
    if (b === 1) return "запрос"
    return "запросов"
}

function sessions(n) {
    var a = Math.abs(n) % 100, b = a % 10
    if (!isRussian()) return n === 1 ? "session" : "sessions"
    if (a > 10 && a < 20) return "сессий"
    if (b > 1 && b < 5) return "сессии"
    if (b === 1) return "сессия"
    return "сессий"
}

function number(n) {
    return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ")
}
