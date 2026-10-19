"""Focused tests for Iron Log progression + rest-timer logic.

Run:  python3 -m unittest test_app -v
Execs only the pure-logic head of app.py (no Streamlit UI is started).
"""
import unittest
from pathlib import Path

APP = Path(__file__).parent / "app.py"
HEAD = APP.read_text(encoding="utf-8").split("# ---------- persistence ----------")[0]
HEAD = HEAD.replace(
    'st.set_page_config(page_title="Iron Log", page_icon="🏋️", layout="centered",\n'
    '                   initial_sidebar_state="collapsed")', "pass")
NS = {"__file__": str(APP)}
exec(compile(HEAD, "app_head", "exec"), NS)


class PrefillTests(unittest.TestCase):
    def setUp(self):
        self.state = NS["seed_state"](NS["load_seed"]())

    def test_completed_pull_prefills_exact_last_session(self):
        # Lat Pulldown last: 50 kg x 9,9,9,9 -> start exactly there, not +1
        self.assertEqual(NS["target_sets_for"](self.state, "Lat Pulldown", 4), [9, 9, 9, 9])
        session = NS["start_session"](self.state, "pull")
        lat = session["exercises"][0]
        self.assertEqual(lat["weight_kg"], 50.0)
        self.assertEqual(lat["targets"], [9, 9, 9, 9])

    def test_weight_is_not_auto_bumped_when_range_topped(self):
        self.state["last"]["Dumbbell Bench Press"] = {
            "weight_kg": 60, "sets": [8, 8, 8, 8], "date": None, "target_reps": "5-8"}
        # Suggestion still flags a weight increase, but the prefill stays at last time
        self.assertEqual(NS["suggestion_for"](self.state, "Dumbbell Bench Press")[0], "weight")
        session = NS["start_session"](self.state, "push")
        self.assertEqual(session["exercises"][0]["weight_kg"], 60.0)
        self.assertEqual(session["exercises"][0]["targets"], [8, 8, 8, 8])

    def test_prefill_uses_most_recent_session_after_finish(self):
        session = NS["start_session"](self.state, "pull")
        NS["finish_session"](self.state, session,
                             [{"exercise": "Lat Pulldown", "weight_kg": 52.5, "sets": [7, 7, 6]}])
        self.assertEqual(NS["target_sets_for"](self.state, "Lat Pulldown", 3), [7, 7, 6])
        nxt = NS["start_session"](self.state, "pull")
        self.assertEqual(nxt["exercises"][0]["weight_kg"], 52.5)

    def test_new_exercise_prefills_range_low_and_zero_weight(self):
        self.assertEqual(NS["target_sets_for"](self.state, "Dumbbell Bench Press", 4), [5, 5, 5, 5])
        session = NS["start_session"](self.state, "push")
        self.assertEqual(session["exercises"][0]["weight_kg"], 0.0)


class FirstUseBaselineTests(unittest.TestCase):
    def test_no_history_reseeds_baseline_from_json_keeps_active_draft(self):
        state = NS["seed_state"](NS["load_seed"]())
        state["last"]["Lat Pulldown"]["weight_kg"] = 999  # stale/drifted
        state["active"] = {"day_type": "push", "current": 0, "exercises": []}
        out = NS["apply_first_use_baseline"](state, NS["seed_state"](NS["load_seed"]()))
        self.assertEqual(out["last"]["Lat Pulldown"]["weight_kg"], 50)
        self.assertEqual(out["last"]["Lat Pulldown"]["sets"], [9, 9, 9, 9])
        self.assertIsNotNone(out["active"])  # in-progress first workout not wiped

    def test_logged_history_locks_baseline_to_logs_not_json(self):
        state = NS["seed_state"](NS["load_seed"]())
        NS["finish_session"](state, NS["start_session"](state, "pull"),
                             [{"exercise": "Lat Pulldown", "weight_kg": 52.5, "sets": [7, 7]}])
        out = NS["apply_first_use_baseline"](state, NS["seed_state"](NS["load_seed"]()))
        self.assertEqual(out["last"]["Lat Pulldown"]["weight_kg"], 52.5)
        self.assertEqual(out["last"]["Lat Pulldown"]["sets"], [7, 7])


class RenameMigrationTests(unittest.TestCase):
    def test_barbell_bench_renamed_everywhere_history_kept(self):
        state = NS["seed_state"](NS["load_seed"]())
        # Simulate an older saved file that still uses the old name
        state["plan"]["push"][0]["name"] = "Barbell Bench Press"
        state["last"]["Barbell Bench Press"] = state["last"].pop("Dumbbell Bench Press")
        state["last"]["Barbell Bench Press"].update({"weight_kg": 20, "sets": [8, 8, 7, 7]})
        state["history"] = [{"id": 1, "date": "2026-10-19T00:00:00+00:00", "day_type": "push",
                             "exercises": [{"exercise": "Barbell Bench Press", "weight_kg": 20, "sets": [8, 8]}]}]
        state["active"] = {"day_type": "push", "current": 0,
                           "exercises": [{"name": "Barbell Bench Press", "weight_kg": 20, "targets": [8, 8, 7, 7]}]}
        out = NS["migrate_state"](state)
        self.assertEqual(out["plan"]["push"][0]["name"], "Dumbbell Bench Press")
        self.assertNotIn("Barbell Bench Press", out["last"])
        self.assertEqual(out["last"]["Dumbbell Bench Press"]["sets"], [8, 8, 7, 7])
        self.assertEqual(out["history"][0]["exercises"][0]["exercise"], "Dumbbell Bench Press")
        self.assertEqual(out["active"]["exercises"][0]["name"], "Dumbbell Bench Press")


class RestTimerTests(unittest.TestCase):
    def test_timer_html_self_refreshes_and_signals_end(self):
        html = NS["rest_timer_html"](1_700_000_090_000)
        self.assertIn("1700000090000", html)      # absolute end time handed to JS
        self.assertIn("setInterval", html)       # ticks without a Streamlit rerun
        self.assertIn("navigator.vibrate", html)
        self.assertIn("Rest over", html)


if __name__ == "__main__":
    unittest.main()
