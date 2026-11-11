"""Claude Pulse for Windows: an icon in the system tray with a dashboard on click.

Usage is collected in a background thread by fetch.py, which runs Claude Code's own
`claude -p /usage`. Notifications are shown as Windows notifications through the tray.
"""
import math
import os
import sys
import time

from PyQt6.QtCore import QLocale, QLockFile, QObject, QRectF, Qt, QThread, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QCursor, QGuiApplication, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtQuick import QQuickView
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from claude_pulse import autostart, fetch

APP_NAME = "Claude Pulse"
BASE = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI = os.path.join(BASE, "claude_pulse", "ui")

# Session and week colours and the icon shape, matching ui/Themes.js.
THEMES = {
    "orbit": ("rings", "#3b82f6", "#d946ef"),
    "lines": ("bars", "#3b82f6", "#a855f7"),
    "terminal": ("bars", "#2563eb", "#9333ea"),
    "battery": ("cells", "#3b82f6", "#a855f7"),
    "paper": ("rings", "#4f7cac", "#8e5ea2"),
}
LABELS = {
    "en": {
        "show": "Show dashboard", "refresh": "Refresh now", "theme": "Theme", "mode": "Appearance", "language": "Language", "autostart": "Start with Windows",
        "config": "Open settings file", "quit": "Quit",
        "orbit": "Orbit", "lines": "Lines", "terminal": "Terminal", "battery": "Battery", "paper": "Paper",
        "system": "Follow the system", "light": "Light", "dark": "Dark", "auto": "System language",
        "plan": "Plan: %s", "line": "%s: %d%% used, %d%% left", "session": "Session", "week": "Week",
        "no_data": "No data yet", "stale": "Could not update: %s",
    },
    "ru": {
        "show": "Открыть панель", "refresh": "Обновить", "theme": "Тема", "mode": "Оформление", "language": "Язык", "autostart": "Запускать вместе с Windows",
        "config": "Открыть файл настроек", "quit": "Выход",
        "orbit": "Орбита", "lines": "Линейки", "terminal": "Терминал", "battery": "Батарея", "paper": "Бумага",
        "system": "Как в системе", "light": "Светлое", "dark": "Тёмное", "auto": "Язык системы",
        "plan": "Тариф: %s", "line": "%s: использовано %d%%, осталось %d%%", "session": "Сессия", "week": "Неделя",
        "no_data": "Данных пока нет", "stale": "Не удалось обновить: %s",
    },
}


def level_color(pct, base):
    return QColor("#ef4444" if pct >= 85 else base)


def render_icon(session, week, risk, theme="orbit"):
    """The tray mark as an icon. session is None on plans with no session limit."""
    shape, session_color, week_color = THEMES.get(theme, THEMES["orbit"])
    size = 64
    track = QColor(128, 128, 128, 110)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    marks = [(session, session_color), (week, week_color)]
    if shape == "rings":
        for (pct, base), inset in zip(marks, (5, 20)):
            if pct is None:
                continue
            rect = QRectF(inset, inset, size - 2 * inset, size - 2 * inset)
            p.setPen(QPen(track, 9))
            p.drawEllipse(rect)
            if pct:
                pen = QPen(level_color(pct, base), 9)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.drawArc(rect, 90 * 16, int(-min(100, pct) / 100 * 360 * 16))
    else:
        p.setPen(Qt.PenStyle.NoPen)
        for (pct, base), top in zip(marks, (12, 38)):
            if pct is None:
                continue
            if shape == "bars":
                p.setBrush(track)
                p.drawRoundedRect(QRectF(2, top, 60, 16), 4, 4)
                p.setBrush(level_color(pct, base))
                p.drawRoundedRect(QRectF(2, top, 60 * min(100, pct) / 100, 16), 4, 4)
            else:
                left = math.ceil((100 - pct) / 100 * 6)
                for i in range(6):
                    p.setBrush(level_color(pct, base) if i < left else track)
                    p.drawRoundedRect(QRectF(2 + i * 10.2, top, 8.6, 16), 2, 2)
    if risk:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#f97316"))
        p.drawEllipse(QRectF(size - 22, 0, 22, 22))
    p.end()
    return QIcon(pixmap)


def system_dark():
    hints = QGuiApplication.styleHints()
    if hasattr(hints, "colorScheme"):  # Qt 6.5+
        return hints.colorScheme() == Qt.ColorScheme.Dark
    return QGuiApplication.palette().window().color().lightnessF() < 0.5


class Worker(QObject):
    """Runs one collection off the UI thread: `claude` can take several seconds."""
    done = pyqtSignal(dict)

    def __init__(self, force):
        super().__init__()
        self.force = force

    def run(self):
        try:
            usage, _ = fetch.update(self.force)
        except Exception as e:  # never let the tray die on an unexpected error
            usage = {"ok": False, "error": str(e)[:160]}
        self.done.emit(usage)


class App:
    def __init__(self):
        self.cfg = fetch.load_settings()
        self.usage = fetch.load_json(fetch.LATEST) if os.path.exists(fetch.LATEST) else None
        if not isinstance(self.usage, dict):
            self.usage = None
        self.busy = False
        self.thread = None
        self.worker = None
        self.board = None

        self.tray = QSystemTrayIcon(render_icon(0, 0, False, self.cfg["theme"]))
        self.tray.setToolTip(APP_NAME)
        self.tray.activated.connect(self.on_activated)
        self.menu = QMenu()
        self.menu.aboutToShow.connect(self.build_menu)
        self.build_menu()
        self.tray.setContextMenu(self.menu)
        self.tray.show()

        self.timer = QTimer()
        self.timer.timeout.connect(lambda: self.refresh(True))
        self.timer.start(int(self.cfg["interval_minutes"] * 60_000))
        hints = QGuiApplication.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(lambda _: self.push())

        self.update_icon()
        self.refresh(True)

    # ----- language and menu -----

    def lang(self):
        return fetch.language(self.cfg)

    def text(self, key):
        return LABELS[self.lang()][key]

    def build_menu(self):
        menu = self.menu
        menu.clear()
        t = self.text

        def add(label, slot, checked=None, parent=menu):
            action = QAction(label, parent)
            if checked is not None:
                action.setCheckable(True)
                action.setChecked(checked)
            action.triggered.connect(slot)
            parent.addAction(action)
            return action

        add(t("show"), self.show_dashboard)
        add(t("refresh"), lambda: self.refresh(True))
        menu.addSeparator()
        for title, key, values in (("theme", "theme", fetch.THEMES), ("mode", "color_mode", ("system", "light", "dark")),
                                   ("language", "language", ("auto", "en", "ru"))):
            sub = menu.addMenu(t(title))
            for value in values:
                label = {"en": "English", "ru": "Русский"}.get(value) or t(value)
                add(label, lambda _, k=key, v=value: self.choose(k, v), self.cfg[key] == value, sub)
        menu.addSeparator()
        if autostart.supported():
            add(t("autostart"), lambda on: autostart.set_enabled(on), autostart.is_enabled())
        add(t("config"), self.open_config)
        menu.addSeparator()
        add(t("quit"), QApplication.quit)

    def choose(self, key, value):
        fetch.save_setting(key, value)
        self.cfg = fetch.load_settings()
        if key == "language":
            self.apply_language()
        self.update_icon()
        self.push()

    def apply_language(self):
        lang = self.cfg["language"]
        QLocale.setDefault(QLocale("ru_RU" if lang == "ru" else "en_US") if lang != "auto" else QLocale.system())
        # QML reads the language once, so rebuild the dashboard.
        if self.board:
            self.board.hide()
            self.board.deleteLater()
            self.board = None

    def open_config(self):
        if not os.path.exists(fetch.CONFIG):
            fetch.save_setting("language", self.cfg["language"])
        if hasattr(os, "startfile"):
            os.startfile(fetch.CONFIG)

    # ----- data -----

    def refresh(self, force):
        if self.busy:
            return
        self.busy = True
        self.push()
        self.thread = QThread()
        self.worker = Worker(force)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.done.connect(self.on_done)
        self.worker.done.connect(self.thread.quit)
        self.thread.start()

    def on_done(self, usage):
        self.busy = False
        alerts = usage.pop("alerts", None) or []
        if usage.get("fetched_at") or not self.usage:
            self.usage = usage
        self.cfg = fetch.load_settings()
        self.timer.setInterval(int(self.cfg["interval_minutes"] * 60_000))
        self.update_icon()
        self.push()
        for summary, body, urgent in alerts:
            icon = QSystemTrayIcon.MessageIcon.Critical if urgent else QSystemTrayIcon.MessageIcon.Warning
            self.tray.showMessage(summary, body, icon, 15000)

    def update_icon(self):
        usage = self.usage or {}
        session = usage.get("session") or {}
        week = usage.get("week") or {}
        risk = bool(session.get("runout") or week.get("runout"))
        self.tray.setIcon(render_icon(session.get("pct", None if week else 0), week.get("pct", 0), risk, self.cfg["theme"]))
        t = self.text
        lines = [APP_NAME]
        if usage.get("plan"):
            lines.append(t("plan") % usage["plan"])
        for key, limit in (("session", session), ("week", week)):
            if limit:
                lines.append(t("line") % (t(key), round(limit["pct"]), 100 - round(limit["pct"])))
        if len(lines) == 1:
            lines.append(t("no_data"))
        if usage.get("ok") is False and usage.get("error"):
            lines.append(t("stale") % usage["error"])
        self.tray.setToolTip("\n".join(lines)[:127])  # Windows cuts tray tips at 127 characters

    def push(self):
        if not self.board or not self.board.rootObject():
            return
        root = self.board.rootObject()
        root.setProperty("busy", self.busy)
        root.setProperty("theme", self.cfg["theme"])
        root.setProperty("colorMode", self.cfg["color_mode"])
        root.setProperty("systemDark", system_dark())
        root.setProperty("now", time.time())
        if self.usage is not None:
            root.setProperty("usage", self.usage)

    def make_view(self, qml, flags):
        view = QQuickView()
        view.setFlags(flags)
        view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
        view.setColor(QColor(Qt.GlobalColor.transparent))
        view.setInitialProperties({
            "usage": self.usage, "theme": self.cfg["theme"], "colorMode": self.cfg["color_mode"],
            "systemDark": system_dark(), "now": time.time(),
        })
        view.setSource(QUrl.fromLocalFile(os.path.join(UI, qml)))
        if view.rootObject() is None:
            raise RuntimeError("; ".join(e.toString() for e in view.errors()))
        return view

    # ----- dashboard -----

    def on_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.toggle_dashboard()

    def build_dashboard(self):
        view = self.make_view("Dashboard.qml", Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                              | Qt.WindowType.WindowStaysOnTopHint)
        root = view.rootObject()
        root.refreshRequested.connect(lambda: self.refresh(True))
        root.implicitHeightChanged.connect(lambda: view.resize(view.width(), int(root.implicitHeight())))
        view.activeChanged.connect(self.on_board_active)
        self.board = view
        self.board_hidden_at = 0

    def on_board_active(self):
        if self.board.isVisible() and not self.board.isActive():
            self.board.hide()
            self.board_hidden_at = time.monotonic()

    def show_dashboard(self):
        if not self.board:
            self.build_dashboard()
        self.push()
        root = self.board.rootObject()
        w, h = int(root.implicitWidth()), int(root.implicitHeight())
        self.board.resize(w, h)
        anchor = self.tray.geometry()
        if anchor.isEmpty():
            pos = QCursor.pos()
            anchor = QRectF(pos.x(), pos.y(), 1, 1).toRect()
        screen = QGuiApplication.screenAt(anchor.center()) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        # Open beside the tray icon, on whichever side has room: works with the taskbar on any edge.
        x = anchor.center().x() - w // 2
        y = anchor.top() - h - 8 if anchor.top() - h - 8 >= area.top() else anchor.bottom() + 8
        x = max(area.left() + 8, min(x, area.right() - w - 8))
        y = max(area.top() + 8, min(y, area.bottom() - h - 8))
        self.board.setPosition(x, y)
        self.board.show()
        self.board.raise_()
        self.board.requestActivate()
        self.refresh(False)

    def toggle_dashboard(self):
        if self.board and self.board.isVisible():
            self.board.hide()
        elif self.board and time.monotonic() - self.board_hidden_at < 0.3:
            pass  # the click that closed it by stealing focus: don't reopen
        else:
            self.show_dashboard()


def selftest():
    """Load every QML file offscreen and exit: used by CI to check a build."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QGuiApplication(sys.argv)
    failures = []
    sample = {"ok": True, "fetched_at": time.time(), "plan": "Max", "models": [], "stats": {}, "history": [],
              "session": {"pct": 42, "reset": time.time() + 3600, "pace": 80, "projected": 52, "runout": 0},
              "week": {"pct": 88, "reset": time.time() + 86400 * 3, "pace": 57, "projected": 150, "runout": time.time() + 9000}}
    for qml in ("Dashboard.qml",):
        view = QQuickView()
        view.setInitialProperties({"usage": sample, "now": time.time()})
        view.setSource(QUrl.fromLocalFile(os.path.join(UI, qml)))
        if view.rootObject() is None or view.errors():
            failures.append(qml + ": " + "; ".join(e.toString() for e in view.errors()))
    render_icon(42, 88, True)
    del app
    if failures and sys.stderr:  # a windowed exe has no stderr
        print("\n".join(failures), file=sys.stderr)
    elif sys.stdout:
        print("selftest ok")
    return 1 if failures else 0


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    if "--text" in sys.argv or "--json" in sys.argv:
        sys.argv = [a for a in sys.argv if a != "--json"]
        fetch.main()
        return
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    os.makedirs(fetch.STATE, exist_ok=True)
    lock = QLockFile(os.path.join(fetch.STATE, "app.lock"))
    if not lock.tryLock(100):
        return  # already running
    app.setWindowIcon(render_icon(40, 70, False))
    autostart.enable_on_first_run()
    cfg = fetch.load_settings()
    if cfg["language"] != "auto":
        QLocale.setDefault(QLocale("ru_RU" if cfg["language"] == "ru" else "en_US"))
    instance = App()
    code = app.exec()
    del instance
    sys.exit(code)


if __name__ == "__main__":
    main()
