import importlib.util
import os
import tempfile
import unittest
from unittest import mock
from datetime import datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("fetch", os.path.join(HERE, "..", "package", "contents", "code", "fetch.py"))
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)

WARSAW = ZoneInfo("Europe/Warsaw")
NOW = datetime(2026, 11, 1, 12, 0, tzinfo=WARSAW).timestamp()
SAMPLE = """You are currently using your subscription to power your Claude Code usage

Current session: 2% used · resets Nov 1, 3:50pm (Europe/Warsaw)
Current week (all models): 36% used · resets Nov 3, 8am (Europe/Warsaw)
Current week (Fable): 10% used · resets Nov 3, 8am (Europe/Warsaw)

Last 24h · 1,494 requests · 9 sessions
  76%  Start fresh when you switch tasks · run /clear
Last 7d · 717 requests · 1 session
"""


def at(*args):
    return datetime(*args, tzinfo=WARSAW).timestamp()


class ParseTests(unittest.TestCase):
    def test_sample(self):
        usage = fetch.parse_usage(SAMPLE, NOW)
        self.assertEqual(usage["session"]["pct"], 2)
        self.assertEqual(usage["session"]["reset"], at(2026, 11, 1, 15, 50))
        self.assertEqual(usage["week"]["pct"], 36)
        self.assertEqual(usage["week"]["reset"], at(2026, 11, 3, 8, 0))
        self.assertEqual([m["name"] for m in usage["models"]], ["Fable"])
        self.assertEqual(usage["stats"]["day"], {"requests": 1494, "sessions": 9})
        self.assertEqual(usage["stats"]["week"], {"requests": 717, "sessions": 1})

    def test_no_reset_time(self):
        usage = fetch.parse_usage("Current session: 0% used\n", NOW)
        self.assertEqual(usage["session"]["pct"], 0)
        self.assertIsNone(usage["session"]["reset"])

    def test_unknown_text_is_ignored(self):
        usage = fetch.parse_usage("<b>Something else</b>\nCurrent week: lots", NOW)
        self.assertIsNone(usage["session"])
        self.assertIsNone(usage["week"])

    def test_noon_and_midnight(self):
        self.assertEqual(fetch.parse_reset("Nov 2, 12am", "Europe/Warsaw", NOW), at(2026, 11, 2, 0, 0))
        self.assertEqual(fetch.parse_reset("Nov 2, 12pm", "Europe/Warsaw", NOW), at(2026, 11, 2, 12, 0))

    def test_time_only_rolls_to_tomorrow(self):
        self.assertEqual(fetch.parse_reset("3pm", "Europe/Warsaw", NOW), at(2026, 11, 1, 15, 0))
        self.assertEqual(fetch.parse_reset("9am", "Europe/Warsaw", NOW), at(2026, 11, 2, 9, 0))

    def test_year_rollover(self):
        late = at(2026, 12, 31, 12, 0)
        self.assertEqual(fetch.parse_reset("Jan 2, 8am", "Europe/Warsaw", late), at(2027, 1, 2, 8, 0))

    def test_bad_dates(self):
        self.assertIsNone(fetch.parse_reset("Feb 31, 8am", "Europe/Warsaw", NOW))
        self.assertIsNone(fetch.parse_reset("soon", "Europe/Warsaw", NOW))
        self.assertIsNotNone(fetch.parse_reset("Nov 3, 8am", "Not/AZone", NOW))


class ForecastTests(unittest.TestCase):
    def test_runs_out(self):
        # 2 of 5 hours gone, 60% used: 100% comes at 3h20, 1h40 before the reset.
        f = fetch.forecast(60, NOW + 3 * 3600, fetch.SESSION_SECONDS, NOW)
        self.assertEqual(f["pace"], 40)
        self.assertEqual(f["projected"], 150)
        self.assertEqual(f["runout"], int(NOW + 4800))

    def test_enough(self):
        f = fetch.forecast(20, NOW + 3 * 3600, fetch.SESSION_SECONDS, NOW)
        self.assertEqual(f["projected"], 50)
        self.assertEqual(f["runout"], 0)

    def test_too_early_has_no_projection(self):
        f = fetch.forecast(30, NOW + fetch.SESSION_SECONDS - 300, fetch.SESSION_SECONDS, NOW)
        self.assertEqual(f["projected"], -1)

    def test_past_reset(self):
        self.assertEqual(fetch.forecast(30, NOW - 60, fetch.SESSION_SECONDS, NOW)["pace"], -1)


def limit(pct, reset=NOW + 3 * 3600, pace=40, runout=0):
    return {"pct": pct, "reset": reset, "pace": pace, "projected": -1, "runout": runout}


class AlertTests(unittest.TestCase):
    cfg = fetch.load_settings({})

    def alerts(self, seen, lim, cfg=None):
        return fetch.pending_alerts([("session", "Session", lim)], seen, cfg or self.cfg, NOW, "en")

    def test_threshold_fires_once(self):
        seen = {}
        self.assertEqual(len(self.alerts(seen, limit(81))), 1)
        self.assertEqual(self.alerts(seen, limit(82)), [])

    def test_reset_jitter_is_the_same_window(self):
        seen = {}
        self.alerts(seen, limit(81))
        self.assertEqual(self.alerts(seen, limit(81, reset=NOW + 3 * 3600 - 60)), [])

    def test_new_window_fires_again(self):
        seen = {}
        self.alerts(seen, limit(81))
        self.assertEqual(len(self.alerts(seen, limit(81, reset=NOW + 4 * 3600))), 1)

    def test_highest_threshold_is_urgent(self):
        alerts = self.alerts({}, limit(96))
        self.assertEqual(len(alerts), 1)
        self.assertTrue(alerts[0][2])

    def test_risk_fires_once(self):
        seen = {}
        lim = limit(60, runout=NOW + 4800)
        alerts = self.alerts(seen, lim)
        self.assertEqual(len(alerts), 1)
        self.assertIn("may hit the limit", alerts[0][0])
        self.assertIn("1 h 40 min", alerts[0][1])
        self.assertEqual(self.alerts(seen, lim), [])

    def test_risk_needs_enough_usage_and_time(self):
        self.assertEqual(self.alerts({}, limit(10, runout=NOW + 4800)), [])
        self.assertEqual(self.alerts({}, limit(60, pace=5, runout=NOW + 4800)), [])

    def test_risk_can_be_turned_off(self):
        cfg = fetch.load_settings({"risk_alerts": False})
        self.assertEqual(self.alerts({}, limit(60, runout=NOW + 4800), cfg), [])

    def test_threshold_and_risk_share_one_message(self):
        seen = {}
        alerts = self.alerts(seen, limit(85, runout=NOW + 1800))
        self.assertEqual(len(alerts), 1)
        self.assertIn("At this pace", alerts[0][1])
        self.assertTrue(seen["session"]["risk"])

    def test_russian(self):
        alerts = fetch.pending_alerts([("week", "Неделя", limit(60, runout=NOW + 4800))], {}, self.cfg, NOW, "ru")
        self.assertIn("риск", alerts[0][0])

    def test_corrupt_state_is_tolerated(self):
        self.assertEqual(len(self.alerts({"session": "junk"}, limit(81))), 1)


class PlanTests(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(fetch.plan_label("max"), "Max")
        self.assertEqual(fetch.plan_label("ultra"), "Ultra")
        self.assertEqual(fetch.plan_label("claude_team_plus"), "Team Plus")

    def test_bad_values_give_nothing(self):
        for value in ("<b>x</b>", "Max 5x", "", "a" * 40, None, 5):
            self.assertIsNone(fetch.plan_label(value))

    def test_plan_without_a_session_limit(self):
        usage = fetch.parse_usage("Current week (all models): 36% used · resets Nov 3, 8am (Europe/Warsaw)\n", NOW)
        self.assertIsNone(usage["session"])
        self.assertEqual(usage["week"]["pct"], 36)
        self.assertIn("Week", fetch.summary(usage))


class LoginTests(unittest.TestCase):
    def run_collect(self, auth, output="", ran=None):
        def fake_run(cfg):
            if ran is not None:
                ran.append(True)
            return output

        with tempfile.TemporaryDirectory() as folder, mock.patch.multiple(
            fetch, LATEST=os.path.join(folder, "latest.json"), HISTORY=os.path.join(folder, "history.jsonl"),
            NOTIFIED=os.path.join(folder, "notified.json"), read_auth=lambda cfg: auth, run_claude=fake_run,
            send_notification=lambda *a: None,
        ):
            return fetch.collect(True, fetch.load_settings({}))

    def test_logged_out_skips_usage(self):
        ran = []
        usage = self.run_collect({"plan": None, "logged_in": False, "method": None}, ran=ran)
        self.assertEqual(usage["error"], fetch.NOT_LOGGED_IN)
        self.assertEqual(ran, [])

    def test_api_key_login_is_explained(self):
        usage = self.run_collect({"plan": None, "logged_in": True, "method": "api_key"}, "no limits here")
        self.assertEqual(usage["error"], fetch.NO_SUBSCRIPTION)

    def test_subscription_without_limits_means_format_change(self):
        usage = self.run_collect({"plan": "Max", "logged_in": True, "method": "claude.ai"}, "new format")
        self.assertEqual(usage["error"], fetch.NO_LIMITS)

    def test_unavailable_status_does_not_block_usage(self):
        usage = self.run_collect({"plan": None, "logged_in": None, "method": None}, SAMPLE)
        self.assertTrue(usage["ok"])
        self.assertEqual(usage["week"]["pct"], 36)

    def test_only_needed_fields_are_kept(self):
        usage = self.run_collect({"plan": "Max", "logged_in": True, "method": "claude.ai"}, SAMPLE)
        self.assertEqual(usage["plan"], "Max")
        self.assertNotIn("method", usage)
        self.assertNotIn("logged_in", usage)


class SettingsTests(unittest.TestCase):
    def test_defaults_on_bad_input(self):
        for raw in ("text", [], {"language": "xx", "interval_minutes": "5", "thresholds": ["a"], "notifications": "no",
                                 "claude_path": "relative/claude", "risk_min_percent": True}):
            self.assertEqual(fetch.load_settings(raw), fetch.DEFAULTS)

    def test_theme_values(self):
        cfg = fetch.load_settings({"theme": "paper", "color_mode": "dark"})
        self.assertEqual((cfg["theme"], cfg["color_mode"]), ("paper", "dark"))
        cfg = fetch.load_settings({"theme": "../evil", "color_mode": "pink"})
        self.assertEqual((cfg["theme"], cfg["color_mode"]), ("orbit", "system"))

    def test_interval_is_clamped(self):
        self.assertEqual(fetch.load_settings({"interval_minutes": 0})["interval_minutes"], 1)
        self.assertEqual(fetch.load_settings({"interval_minutes": 9999})["interval_minutes"], 60)

    def test_valid_values(self):
        cfg = fetch.load_settings({"language": "ru", "thresholds": [90, 50], "notifications": False})
        self.assertEqual(cfg["language"], "ru")
        self.assertEqual(cfg["thresholds"], [50, 90])
        self.assertFalse(cfg["notifications"])


if __name__ == "__main__":
    unittest.main()
