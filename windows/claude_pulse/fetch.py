#!/usr/bin/env python3
"""Collect Claude Code usage through the official `claude -p /usage` command.

The command is local to Claude Code: it costs no tokens and Claude Code handles
its own login, so this module never reads credentials and opens no network
connections itself. Run it directly to print one JSON document to stdout (or a
short summary with --text). The last good result is kept and returned on failure.

Works on Windows first, and on Linux and macOS for development and tests.
"""
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

WINDOWS = os.name == "nt"
if WINDOWS:
    STATE = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local"), "claude-pulse")
    CONFIG = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~\\AppData\\Roaming"), "claude-pulse", "config.json")
else:
    STATE = os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"), "claude-pulse")
    CONFIG = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "claude-pulse", "config.json")
LATEST = os.path.join(STATE, "latest.json")
HISTORY = os.path.join(STATE, "history.jsonl")
NOTIFIED = os.path.join(STATE, "notified.json")
UNPARSED = os.path.join(STATE, "last-usage-output.txt")

MIN_AGE = 45  # seconds between real calls unless --force
HISTORY_KEEP = 8 * 86400
SESSION_SECONDS = 5 * 3600
WEEK_SECONDS = 7 * 86400
SAME_WINDOW_SLACK = 1800  # /usage rounds reset times, so they drift by a minute or so
RISK_MIN_PACE = 15  # percent of the window that must pass before a projection can alarm
THEMES = ("orbit", "lines", "terminal", "battery", "paper")
MONTHS = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}

DEFAULTS = {
    "language": "auto",
    "theme": "orbit",
    "color_mode": "system",
    "interval_minutes": 5,
    "claude_path": "",
    "notifications": True,
    "thresholds": [80, 95],
    "risk_alerts": True,
    "risk_min_percent": 20,
}
# Keep the console window of `claude` (a console program) from flashing up.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# /usage is text for people, and its layout differs between versions and platforms:
# "Current session: 2% used · resets 3:50pm (Europe/Warsaw)" on one line, or the
# header, the bar with "2% used" and "Resets 3:50pm" on lines of their own. So the
# header, the percentage and the reset are found separately rather than as one line.
HEAD_RE = re.compile(r"Current (session|week)(?: \(([^)]+)\))?", re.I)
PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%\s*used", re.I)
RESETS_RE = re.compile(r"\bresets?\s+(.+?)(?:\s+\(([^)]+)\))?\s*$", re.I)
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07")
RESET_RE = re.compile(r"^(?:([A-Z][a-z]{2}) (\d{1,2})(?:, (\d{4}))?)?,?\s*(?:(\d{1,2})(?::(\d{2}))?\s*([ap]m))?$", re.I)
STATS_RE = re.compile(r"Last (24h|7d)\W+([\d,  ]+) requests?\W+([\d,  ]+) sessions?", re.I)
NOT_LOGGED_IN = "Not logged in to Claude Code. Run claude and log in"
NO_SUBSCRIPTION = "This login has no subscription limits. Log in to Claude Code with a subscription"
NO_LIMITS = "No limits in /usage output. Its format may have changed"
OLD_CLAUDE = "This Claude Code can't run /usage with -p. Update it: claude update"
UNKNOWN_RE = re.compile(r"unknown (?:skill|command|slash command)", re.I)

PLAN_RE = re.compile(r"^[a-z][a-z0-9_]{0,23}$")

TEXT = {
    "en": {
        "session": "Session", "week": "Week", "day": "d", "hour": "h", "minute": "min",
        "used": "{title}: {pct}% used", "left": "{left}% left",
        "risk_title": "Claude: you may hit the limit",
        "risk_body": "{title}: {pct}% used. At this pace it runs out at {at}, {gap} before the reset.",
        "risk_gap_only": "At this pace it runs out at {at}, {gap} before the reset.",
    },
    "ru": {
        "session": "Сессия", "week": "Неделя", "day": "д", "hour": "ч", "minute": "мин",
        "used": "{title}: использовано {pct}%", "left": "Осталось {left}%",
        "risk_title": "Claude: риск упереться в лимит",
        "risk_body": "{title}: использовано {pct}%. При таком темпе лимит кончится в {at}, за {gap} до сброса.",
        "risk_gap_only": "При таком темпе лимит кончится в {at}, за {gap} до сброса.",
    },
}


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def load_settings(raw=None):
    """Merge the user's config over the defaults, ignoring invalid values."""
    if raw is None:
        raw = load_json(CONFIG)
    cfg = dict(DEFAULTS)
    if not isinstance(raw, dict):
        return cfg
    if raw.get("language") in ("auto", "en", "ru"):
        cfg["language"] = raw["language"]
    if raw.get("theme") in THEMES:
        cfg["theme"] = raw["theme"]
    if raw.get("color_mode") in ("system", "light", "dark"):
        cfg["color_mode"] = raw["color_mode"]
    minutes = raw.get("interval_minutes")
    if isinstance(minutes, (int, float)) and not isinstance(minutes, bool):
        cfg["interval_minutes"] = max(1, min(60, minutes))
    path = raw.get("claude_path")
    if isinstance(path, str) and os.path.isabs(path):
        cfg["claude_path"] = path
    for key in ("notifications", "risk_alerts"):
        if isinstance(raw.get(key), bool):
            cfg[key] = raw[key]
    levels = raw.get("thresholds")
    if isinstance(levels, list) and all(isinstance(t, (int, float)) and not isinstance(t, bool) and 0 < t <= 100 for t in levels):
        cfg["thresholds"] = sorted(levels)
    floor = raw.get("risk_min_percent")
    if isinstance(floor, (int, float)) and not isinstance(floor, bool) and 0 <= floor <= 100:
        cfg["risk_min_percent"] = floor
    return cfg


def save_setting(key, value):
    """Change one key of the config file, keeping the others."""
    config = load_json(CONFIG)
    if not isinstance(config, dict):
        config = {}
    config[key] = value
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    tmp = CONFIG + ".tmp"
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG)


def language(cfg):
    if cfg["language"] != "auto":
        return cfg["language"]
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var)
        if value:
            return "ru" if value.lower().startswith("ru") else "en"
    if WINDOWS:
        try:
            import ctypes
            # LANG_RUSSIAN is 0x19 in the low bits of the language id.
            return "ru" if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x19 else "en"
        except (AttributeError, OSError):
            pass
    return "en"


def parse_reset(text, tz_name, now):
    """Turn 'Nov 3, 8am' or '3:50pm' into epoch seconds; None if unrecognised."""
    if not text:
        return None
    m = RESET_RE.match(text.strip())
    if not m or not (m.group(1) or m.group(4)):
        return None
    try:
        tz = ZoneInfo(tz_name) if tz_name else None
    except Exception:
        tz = None
    local_now = datetime.fromtimestamp(now, tz)
    month, day, year, hour, minute, ampm = m.groups()
    h = 0
    if hour:
        h = int(hour) % 12 + (12 if ampm.lower() == "pm" else 0)
    try:
        if month:
            mon = MONTHS.get(month.title())
            if not mon:
                return None
            dt = local_now.replace(year=int(year) if year else local_now.year, month=mon, day=int(day),
                                   hour=h, minute=int(minute or 0), second=0, microsecond=0)
            if not year and dt < local_now - timedelta(days=180):
                dt = dt.replace(year=dt.year + 1)
        else:
            dt = local_now.replace(hour=h, minute=int(minute or 0), second=0, microsecond=0)
            if dt < local_now:
                dt += timedelta(days=1)
    except ValueError:
        return None
    return int(dt.timestamp())


def forecast(pct, reset, duration, now):
    """Straight-line projection of the window: pace, projected use, run-out time."""
    if not reset:
        return {"pace": -1, "projected": -1, "runout": 0}
    elapsed = duration - (reset - now)
    if elapsed <= 0 or elapsed > duration:
        return {"pace": -1, "projected": -1, "runout": 0}
    result = {"pace": round(elapsed / duration * 100, 1), "projected": -1, "runout": 0}
    # Too early in the window a projection is noise.
    if elapsed >= duration * 0.05 and pct > 0:
        rate = pct / elapsed
        result["projected"] = round(pct + rate * (reset - now), 1)
        if pct < 100 and result["projected"] >= 100:
            result["runout"] = int(now + (100 - pct) / rate)
    return result


def parse_usage(text, now):
    out = {"session": None, "week": None, "models": [], "stats": {}}
    found = []  # [kind, model, pct, reset text, time zone]
    for raw in ANSI_RE.sub("", text).splitlines():
        line = raw.strip()
        m = STATS_RE.search(line)
        if m:
            key = "day" if m.group(1).lower() == "24h" else "week"
            out["stats"][key] = {"requests": int(re.sub(r"\D", "", m.group(2))),
                                 "sessions": int(re.sub(r"\D", "", m.group(3)))}
            found.append(None)  # a stats line ends the current limit block
            continue
        rest = line
        m = HEAD_RE.search(line)
        if m:
            found.append([m.group(1).lower(), m.group(2), None, None, None])
            rest = line[m.end():]
        current = found[-1] if found else None
        if current is None:
            continue
        if current[2] is None:
            p = PCT_RE.search(rest)
            if p:
                current[2] = float(p.group(1))
                rest = rest[p.end():]
        if current[3] is None:
            r = RESETS_RE.search(rest)
            if r:
                current[3], current[4] = re.sub(r"^(?:at|on)\s+", "", r.group(1).strip(" ·-–—,.")), r.group(2)
    for item in found:
        if not item or item[2] is None:
            continue
        kind, model, pct, reset_text, tz = item
        reset = parse_reset(reset_text, tz, now)
        if kind == "session":
            out["session"] = {"pct": pct, "reset": reset, **forecast(pct, reset, SESSION_SECONDS, now)}
        elif model and model.lower() != "all models":
            out["models"].append({"name": model, "pct": pct, "reset": reset, **forecast(pct, reset, WEEK_SECONDS, now)})
        else:
            out["week"] = {"pct": pct, "reset": reset, **forecast(pct, reset, WEEK_SECONDS, now)}
    return out


def plan_label(kind):
    """'max' becomes 'Max'. Names aren't listed, so a renamed plan still shows up."""
    if not isinstance(kind, str) or not PLAN_RE.match(kind):
        return None
    return kind.removeprefix("claude_").replace("_", " ").title()


def claude_binary(cfg):
    """Where `claude` lives: the setting, PATH, then the usual install folders.

    The panel or Explorer can start us with a shorter PATH than a terminal has, so
    the native installer's and npm's folders are checked by hand too.
    """
    if cfg["claude_path"]:
        return cfg["claude_path"]
    found = shutil.which("claude")
    if found:
        return found
    if WINDOWS:
        candidates = [os.path.expanduser("~\\.local\\bin\\claude.exe")]
        if os.environ.get("APPDATA"):
            candidates.append(os.path.join(os.environ["APPDATA"], "npm", "claude.cmd"))
        if os.environ.get("LOCALAPPDATA"):
            candidates.append(os.path.join(os.environ["LOCALAPPDATA"], "Programs", "claude", "claude.exe"))
    else:
        candidates = [os.path.expanduser("~/.local/bin/claude")]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return candidates[0]


def run(args, **kwargs):
    """subprocess.run with UTF-8 output (Windows defaults to the ANSI code page) and no console window."""
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          stdin=subprocess.DEVNULL, creationflags=NO_WINDOW, cwd=STATE, **kwargs)


def read_auth(cfg):
    """Plan and login state from `claude auth status`. Email and organisation are ignored."""
    auth = {"plan": None, "logged_in": None, "method": None}
    try:
        proc = run([claude_binary(cfg), "auth", "status", "--json"], timeout=20)
        status = json.loads(proc.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return auth
    if isinstance(status, dict):
        auth["plan"] = plan_label(status.get("subscriptionType"))
        if isinstance(status.get("loggedIn"), bool):
            auth["logged_in"] = status["loggedIn"]
        if isinstance(status.get("authMethod"), str):
            auth["method"] = status["authMethod"]
    return auth


def run_claude(cfg):
    binary = claude_binary(cfg)
    if not os.path.isfile(binary) or not os.access(binary, os.X_OK):
        raise RuntimeError("claude not found")
    # Don't pass on the variables of a Claude Code session we may have been started from.
    # The Git Bash path is user configuration that Claude Code on Windows needs, so it stays.
    env = {k: v for k, v in os.environ.items()
           if (not k.startswith("CLAUDE_CODE_") or k == "CLAUDE_CODE_GIT_BASH_PATH") and k != "CLAUDECODE"}
    # cwd is our private state folder, so no project's settings or hooks apply.
    proc = run([binary, "-p", "/usage", "--output-format", "json", "--no-session-persistence", "--strict-mcp-config"],
               timeout=90, env=env)
    try:
        doc = json.loads(proc.stdout)
    except ValueError:
        raise RuntimeError("claude returned non-JSON output (exit code %d)" % proc.returncode)
    if not isinstance(doc, dict):
        raise RuntimeError("claude returned unexpected output")
    if doc.get("is_error"):
        raise RuntimeError(str(doc.get("result") or "claude reported an error")[:160])
    return str(doc.get("result") or "")


def update_history(session, week, now):
    rows = []
    try:
        with open(HISTORY, encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, list) and len(row) == 3 and isinstance(row[0], (int, float)) and row[0] >= now - HISTORY_KEEP:
                    rows.append(row)
    except OSError:
        pass
    rows.append([int(now), session["pct"] if session else None, week["pct"] if week else None])
    tmp = HISTORY + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r) + "\n" for r in rows)
    os.replace(tmp, HISTORY)
    return rows


def format_duration(seconds, text):
    minutes = max(1, int(seconds // 60))
    d, h, m = minutes // 1440, minutes % 1440 // 60, minutes % 60
    if d:
        return "%d %s %d %s" % (d, text["day"], h, text["hour"])
    if h:
        return "%d %s %d %s" % (h, text["hour"], m, text["minute"])
    return "%d %s" % (m, text["minute"])


def format_clock(epoch, now):
    t, n = datetime.fromtimestamp(epoch), datetime.fromtimestamp(now)
    return t.strftime("%H:%M") if t.date() == n.date() else t.strftime("%d.%m %H:%M")


def is_at_risk(limit, cfg):
    """A forecast worth interrupting for: it runs out early, and it's not just noise."""
    return bool(limit.get("runout") and limit.get("pace", -1) >= RISK_MIN_PACE
                and limit["pct"] >= cfg["risk_min_percent"])


def pending_alerts(windows, seen, cfg, now, lang):
    """Work out which notifications are due. Each one fires once per limit window.

    windows: (key, title, limit). Updates `seen` and returns (summary, body, urgent).
    """
    text = TEXT[lang]
    alerts = []
    for key, title, limit in windows:
        pct, reset = limit["pct"], limit.get("reset")
        mark = seen.get(key)
        if isinstance(mark, dict) and isinstance(mark.get("reset"), (int, float)) and reset:
            fresh = abs(mark["reset"] - reset) > SAME_WINDOW_SLACK
        else:
            fresh = not (isinstance(mark, dict) and mark.get("reset") == reset)
        if fresh:
            mark = {"reset": reset, "level": 0, "risk": False}
        crossed = [t for t in cfg["thresholds"] if pct >= t and t > mark.get("level", 0)]
        risk = cfg["risk_alerts"] and not mark.get("risk") and is_at_risk(limit, cfg)
        gap = None
        if risk:
            gap = dict(at=format_clock(limit["runout"], now), gap=format_duration(limit["reset"] - limit["runout"], text))
        shown = int(round(pct))
        if crossed:
            mark["level"] = crossed[-1]
            body = text["left"].format(left=max(0, 100 - shown))
            if risk:
                body += ". " + text["risk_gap_only"].format(**gap)
            alerts.append((text["used"].format(title=title, pct=shown), body, crossed[-1] >= 95))
        elif risk:
            alerts.append((text["risk_title"], text["risk_body"].format(title=title, pct=shown, **gap), False))
        if risk:
            mark["risk"] = True
        seen[key] = mark
    return alerts


def due_alerts(usage, cfg, now):
    """Alerts to show now, as (summary, body, urgent). The tray app shows them as Windows notifications."""
    if not cfg["notifications"]:
        return []
    lang = language(cfg)
    text = TEXT[lang]
    windows = []
    if usage["session"]:
        windows.append(("session", text["session"], usage["session"]))
    if usage["week"]:
        windows.append(("week", text["week"], usage["week"]))
    for model in usage["models"]:
        windows.append(("week:" + model["name"], "%s (%s)" % (text["week"], model["name"]), model))
    seen = load_json(NOTIFIED)
    if not isinstance(seen, dict):
        seen = {}
    before = json.dumps(seen, sort_keys=True)
    alerts = pending_alerts(windows, seen, cfg, now, lang)
    if json.dumps(seen, sort_keys=True) != before:
        write_json(NOTIFIED, seen)
    return alerts


def collect(force, cfg):
    now = time.time()
    latest = load_json(LATEST)
    if not isinstance(latest, dict):
        latest = None
    if not force and latest and latest.get("ok") and now - latest.get("fetched_at", 0) < MIN_AGE:
        return latest
    auth = read_auth(cfg)
    try:
        if auth["logged_in"] is False:
            raise RuntimeError(NOT_LOGGED_IN)
        output = run_claude(cfg)
        usage = parse_usage(output, now)
        if not usage["session"] and not usage["week"]:
            # Keep what came back so a format change can be looked at. /usage holds no secrets.
            try:
                with open(UNPARSED, "w", encoding="utf-8") as f:
                    f.write(output)
            except OSError:
                pass
            if UNKNOWN_RE.search(output):
                raise RuntimeError(OLD_CLAUDE)
            raise RuntimeError(NO_SUBSCRIPTION if auth["method"] not in (None, "claude.ai") else NO_LIMITS)
    except (RuntimeError, OSError, subprocess.SubprocessError) as e:
        stale = dict(latest or {})
        stale.update(ok=False, error=str(e), failed_at=int(now))
        return stale
    usage.update(ok=True, error="", fetched_at=int(now), plan=auth["plan"])
    usage["history"] = update_history(usage["session"], usage["week"], now)
    write_json(LATEST, usage)
    try:
        usage["alerts"] = due_alerts(usage, cfg, now)
    except OSError:
        usage["alerts"] = []
    return usage


def summary(usage):
    parts = ["Plan " + usage["plan"]] if usage.get("plan") else []
    for name, key in (("Session", "session"), ("Week", "week")):
        limit = usage.get(key)
        if limit:
            parts.append("%s %d%% used, %d%% left" % (name, round(limit["pct"]), 100 - round(limit["pct"])))
    if usage.get("error"):
        parts.append("(stale: %s)" % usage["error"])
    return "; ".join(parts) or "no data"


@contextlib.contextmanager
def state_lock():
    """One update at a time, even with the app and a terminal both asking."""
    if not WINDOWS:
        os.umask(0o077)
    os.makedirs(STATE, mode=0o700, exist_ok=True)
    if not WINDOWS:
        os.chmod(STATE, 0o700)  # on Windows the folder inherits the user-only ACL of %LOCALAPPDATA%
    with open(os.path.join(STATE, "lock"), "a+") as lock:
        if WINDOWS:
            import msvcrt
            lock.seek(0)
            while True:
                try:
                    msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)  # retries for about 10 s, then raises
                    break
                except OSError:
                    continue
            try:
                yield
            finally:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield


def update(force=False):
    """Load settings, collect under the lock and attach the settings the UI needs."""
    cfg = load_settings()
    with state_lock():
        usage = collect(force, cfg)
    usage["settings"] = {"language": cfg["language"], "interval_minutes": cfg["interval_minutes"],
                         "theme": cfg["theme"], "color_mode": cfg["color_mode"]}
    return usage, cfg


def main():
    usage, _ = update("--force" in sys.argv)
    usage.pop("alerts", None)
    if sys.stdout:  # None in the windowed exe
        print(summary(usage) if "--text" in sys.argv else json.dumps(usage, ensure_ascii=False))


if __name__ == "__main__":
    main()
