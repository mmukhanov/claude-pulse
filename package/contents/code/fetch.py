#!/usr/bin/env python3
"""Collect Claude Code usage through the official `claude -p /usage` command.

The command is local to Claude Code: it costs no tokens and Claude Code handles
its own login, so this script never reads credentials and opens no network
connections itself. Prints one JSON document to stdout (or a short summary with
--text). The last good result is kept and returned on failure.
"""
import fcntl
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

STATE = os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"), "claude-pulse")
CONFIG = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "claude-pulse", "config.json")
LATEST = os.path.join(STATE, "latest.json")
HISTORY = os.path.join(STATE, "history.jsonl")
NOTIFIED = os.path.join(STATE, "notified.json")

MIN_AGE = 45  # seconds between real calls unless --force
HISTORY_KEEP = 8 * 86400
SESSION_SECONDS = 5 * 3600
WEEK_SECONDS = 7 * 86400
SAME_WINDOW_SLACK = 1800  # /usage rounds reset times, so they drift by a minute or so
RISK_MIN_PACE = 15  # percent of the window that must pass before a projection can alarm
MONTHS = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}

DEFAULTS = {
    "language": "auto",
    "interval_minutes": 5,
    "claude_path": "",
    "notifications": True,
    "thresholds": [80, 95],
    "risk_alerts": True,
    "risk_min_percent": 20,
}

LIMIT_RE = re.compile(
    r"^Current (session|week)(?: \((.+?)\))?:\s*(\d+(?:\.\d+)?)% used"
    r"(?:\s*·\s*resets\s+(.+?)(?:\s+\(([^)]+)\))?)?\s*$"
)
RESET_RE = re.compile(r"^(?:([A-Z][a-z]{2}) (\d{1,2})(?:, (\d{4}))?)?,?\s*(?:(\d{1,2})(?::(\d{2}))?\s*([ap]m))?$", re.I)
STATS_RE = re.compile(r"^Last (24h|7d) · ([\d,]+) requests? · ([\d,]+) sessions?")

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


def language(cfg):
    if cfg["language"] != "auto":
        return cfg["language"]
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var)
        if value:
            return "ru" if value.lower().startswith("ru") else "en"
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
    for raw in text.splitlines():
        line = raw.strip()
        m = LIMIT_RE.match(line)
        if m:
            kind, model, pct, reset_text, tz = m.groups()
            pct = float(pct)
            reset = parse_reset(reset_text, tz, now)
            if kind == "session":
                out["session"] = {"pct": pct, "reset": reset, **forecast(pct, reset, SESSION_SECONDS, now)}
            elif model and model.lower() != "all models":
                out["models"].append({"name": model, "pct": pct, "reset": reset, **forecast(pct, reset, WEEK_SECONDS, now)})
            else:
                out["week"] = {"pct": pct, "reset": reset, **forecast(pct, reset, WEEK_SECONDS, now)}
            continue
        m = STATS_RE.match(line)
        if m:
            key = "day" if m.group(1) == "24h" else "week"
            out["stats"][key] = {"requests": int(m.group(2).replace(",", "")),
                                 "sessions": int(m.group(3).replace(",", ""))}
    return out


def run_claude(cfg):
    binary = cfg["claude_path"] or shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")
    if not os.access(binary, os.X_OK):
        raise RuntimeError("claude not found")
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE_CODE_") and k != "CLAUDECODE"}
    # cwd is our private state folder, so no project's settings or hooks apply.
    proc = subprocess.run(
        [binary, "-p", "/usage", "--output-format", "json", "--no-session-persistence", "--strict-mcp-config"],
        capture_output=True, text=True, timeout=90, cwd=STATE, env=env, stdin=subprocess.DEVNULL,
    )
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


def send_notification(summary, body, urgent):
    subprocess.run(["notify-send", "-a", "Claude Pulse", "-i", "dialog-warning", "-u", "critical" if urgent else "normal",
                    "--", html.escape(summary, quote=False), html.escape(body, quote=False)],
                   check=False, timeout=10, stderr=subprocess.DEVNULL)


def notify(usage, cfg, now):
    if not cfg["notifications"]:
        return
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
    for alert in alerts:
        send_notification(*alert)


def collect(force, cfg):
    now = time.time()
    latest = load_json(LATEST)
    if not isinstance(latest, dict):
        latest = None
    if not force and latest and latest.get("ok") and now - latest.get("fetched_at", 0) < MIN_AGE:
        return latest
    try:
        usage = parse_usage(run_claude(cfg), now)
        if not usage["session"] and not usage["week"]:
            raise RuntimeError("no limits in /usage output (API key login, or the format changed)")
    except (RuntimeError, OSError, subprocess.SubprocessError) as e:
        stale = dict(latest or {})
        stale.update(ok=False, error=str(e), failed_at=int(now))
        return stale
    usage.update(ok=True, error="", fetched_at=int(now))
    usage["history"] = update_history(usage["session"], usage["week"], now)
    write_json(LATEST, usage)
    try:
        notify(usage, cfg, now)
    except (OSError, subprocess.SubprocessError):
        pass  # no notification daemon or notify-send: the numbers still work
    return usage


def summary(usage):
    parts = []
    for name, key in (("Session", "session"), ("Week", "week")):
        limit = usage.get(key)
        if limit:
            parts.append("%s %d%% used, %d%% left" % (name, round(limit["pct"]), 100 - round(limit["pct"])))
    if usage.get("error"):
        parts.append("(stale: %s)" % usage["error"])
    return "; ".join(parts) or "no data"


def main():
    os.umask(0o077)
    os.makedirs(STATE, mode=0o700, exist_ok=True)
    os.chmod(STATE, 0o700)
    cfg = load_settings()
    with open(os.path.join(STATE, "lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        usage = collect("--force" in sys.argv, cfg)
    usage["settings"] = {"language": cfg["language"], "interval_minutes": cfg["interval_minutes"]}
    print(summary(usage) if "--text" in sys.argv else json.dumps(usage, ensure_ascii=False))


if __name__ == "__main__":
    main()
