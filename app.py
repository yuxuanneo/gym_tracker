"""Iron Log — Streamlit workout tracker (Push / Pull / Legs).

Run:  streamlit run app.py
Data: seeded from workout_splits.json; progress persists to progress.json
      (export/import a backup from the Data tab — see README).
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

import streamlit as st
import streamlit.components.v1 as components

BASE = Path(__file__).parent
SEED_FILE = BASE / "workout_splits.json"
PROGRESS_FILE = BASE / "progress.json"
DAYS = ["push", "pull", "legs"]
WEIGHT_STEP = 2.5

st.set_page_config(page_title="Iron Log", page_icon="🏋️", layout="centered",
                   initial_sidebar_state="collapsed")

st.markdown("""
<style>
.stButton>button, .stDownloadButton>button {min-height:56px; font-size:17px; font-weight:700; border-radius:14px;}
div[data-testid="stNumberInput"] input {font-size:20px; font-weight:700; text-align:center;}
div[data-testid="stCheckbox"] label {font-size:16px;}
.block-container {padding-top:1.2rem; max-width:720px;}
a[data-testid="stLinkButton"] {min-height:44px; border-radius:12px;}
</style>
""", unsafe_allow_html=True)


# ---------- pure progression / data logic (also exercised by tests) ----------
def yt_url(name: str) -> str:
    return "https://www.youtube.com/results?search_query=" + quote_plus(f"{name} proper form tutorial")


def parse_range(text):
    if not text:
        return None
    parts = str(text).replace("–", "-").split("-")
    try:
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return None


def load_seed() -> dict:
    return json.loads(SEED_FILE.read_text(encoding="utf-8"))


RENAMES = {"Barbell Bench Press": "Dumbbell Bench Press"}


def apply_first_use_baseline(state: dict, seeded: dict) -> dict:
    """Before the first logged workout, the baseline (plan + last weight/reps)
    comes from workout_splits.json, so edits to that file still take effect.
    Once anything is in history, logged workouts are the baseline and the
    JSON is never re-applied. An in-progress draft is always kept."""
    if state.get("history"):
        return state
    active = state.get("active")
    seeded["active"] = active
    return seeded


def migrate_state(state: dict) -> dict:
    """Rename exercises in plan, last, history and any in-progress workout,
    so saved data from before a rename keeps its weights and history."""
    for day in state.get("plan", {}).values():
        for ex in day:
            ex["name"] = RENAMES.get(ex["name"], ex["name"])
    last = state.get("last", {})
    for old, new in RENAMES.items():
        if old in last:
            last.setdefault(new, last.pop(old))
            if new != old and old in last:
                last.pop(old)
    for h in state.get("history", []):
        for e in h.get("exercises", []):
            e["exercise"] = RENAMES.get(e["exercise"], e["exercise"])
    active = state.get("active") or {}
    for e in active.get("exercises", []):
        e["name"] = RENAMES.get(e["name"], e["name"])
    return state


def seed_state(seed: dict) -> dict:
    plan, last = {}, {}
    for w in seed["workouts"]:
        plan[w["day_type"]] = [
            {"name": e["exercise"],
             "sets_count": len(e["sets"]) if isinstance(e.get("sets"), list) else int(e.get("sets", 3)),
             "target_reps": e.get("target_reps"),
             "drop_set": bool(e.get("drop_set"))}
            for e in w["exercises"]]
        for e in w["exercises"]:
            last[e["exercise"]] = (
                {"weight_kg": e["weight_kg"], "sets": list(e["sets"]), "date": None,
                 "target_reps": e.get("target_reps")}
                if e.get("weight_kg") is not None else
                {"weight_kg": None, "sets": None, "date": None,
                 "target_reps": e.get("target_reps")})
    return {"plan": plan, "last": last, "history": [], "active": None}


def next_day(history: list) -> str:
    if not history:
        return "push"
    return DAYS[(DAYS.index(history[0]["day_type"]) + 1) % len(DAYS)]


def suggestion_for(state: dict, name: str):
    """Return (kind, message): 'weight' = add weight, 'rep' = +1 rep, 'new'."""
    last = state["last"].get(name) or {}
    ex = next((e for d in state["plan"].values() for e in d if e["name"] == name), {})
    rng = parse_range(last.get("target_reps") or ex.get("target_reps"))
    sets = last.get("sets")
    if sets:
        if rng and all(r >= rng[1] for r in sets):
            return "weight", (f"Hit {rng[1]} reps on every set last time → add "
                              f"+{WEIGHT_STEP:g} kg today, rebuild from {rng[0]} reps")
        if not rng and all(r >= 12 for r in sets):
            return "weight", f"12+ reps on every set last time → try +{WEIGHT_STEP:g} kg today"
        return "rep", (f"Last: {last.get('weight_kg')} kg × {', '.join(map(str, sets))} "
                       f"→ aim +1 rep per set today")
    if rng:
        return "new", f"New — start light, aim {rng[0]}–{rng[1]} reps and log your weight"
    return "new", "New — log your first weight & reps"


def target_sets_for(state: dict, name: str, sets_count: int) -> list:
    """Pre-fill = exactly what you did last time (most recent session for
    this exercise). The +1 rep / +weight goals stay as suggestions only."""
    last = state["last"].get(name) or {}
    ex = next((e for d in state["plan"].values() for e in d if e["name"] == name), {})
    rng = parse_range(last.get("target_reps") or ex.get("target_reps"))
    if last.get("sets"):
        reps = list(last["sets"])
    elif rng:
        reps = [rng[0]] * sets_count
    else:
        reps = [10] * sets_count
    return (reps + [reps[-1] if reps else 10] * sets_count)[:sets_count]


def rest_timer_html(end_ms: int) -> str:
    """Self-refreshing countdown. Streamlit only reruns on interaction, so
    the ticking runs client-side in JS against an absolute end time."""
    return f"""
<div style="font-family:sans-serif;text-align:center;color:#f2f3ee">
  <div style="font-size:13px;font-weight:700;letter-spacing:.08em;color:#9aa39a">REST REMAINING</div>
  <div id="t" style="font-size:44px;font-weight:900;line-height:1.1">--:--</div>
</div>
<script>
const END = {int(end_ms)};
let signalled = false;
function tick() {{
  const left = Math.max(0, Math.ceil((END - Date.now()) / 1000));
  const el = document.getElementById('t');
  if (left > 0) {{
    el.textContent = String(Math.floor(left / 60)).padStart(2, '0') + ':' + String(left % 60).padStart(2, '0');
  }} else {{
    el.textContent = 'Rest over — next set';
    el.style.color = '#3ddc84'; el.style.fontSize = '26px';
    if (!signalled) {{ signalled = true;
      try {{ navigator.vibrate && navigator.vibrate([120, 60, 120]); }} catch (e) {{}}
      try {{ const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const o = ctx.createOscillator(), g = ctx.createGain();
        o.connect(g); g.connect(ctx.destination); o.frequency.value = 880;
        g.gain.setValueAtTime(0.15, ctx.currentTime);
        o.start(); o.stop(ctx.currentTime + 0.25); }} catch (e) {{}}
    }}
  }}
}}
tick(); setInterval(tick, 250);
</script>"""


def start_session(state: dict, day: str) -> dict:
    exercises = []
    for ex in state["plan"][day]:
        last = state["last"].get(ex["name"]) or {}
        weight = float(last["weight_kg"]) if last.get("weight_kg") is not None else 0.0
        exercises.append({"name": ex["name"], "weight_kg": weight,
                          "target_reps": ex.get("target_reps") or last.get("target_reps"),
                          "drop_set": ex["drop_set"],
                          "targets": target_sets_for(state, ex["name"], ex["sets_count"])})
    return {"day_type": day, "started_at": datetime.now(timezone.utc).isoformat(),
            "current": 0, "exercises": exercises}


def finish_session(state: dict, active: dict, logged: list) -> dict:
    """logged: [{exercise, weight_kg, sets:[done reps]}]. Updates last + history."""
    done_ex = [e for e in logged if e["sets"]]
    if not done_ex:
        raise ValueError("Mark at least one set as done first.")
    entry = {"id": int(time.time() * 1000),
             "date": datetime.now(timezone.utc).isoformat(),
             "day_type": active["day_type"], "exercises": done_ex}
    for e in done_ex:
        prev = state["last"].get(e["exercise"]) or {}
        state["last"][e["exercise"]] = {
            "weight_kg": e["weight_kg"], "sets": list(e["sets"]), "date": entry["date"],
            "target_reps": e.get("target_reps") or prev.get("target_reps")}
    state["history"].insert(0, entry)
    state["active"] = None
    return entry


def export_payload(state: dict) -> dict:
    workouts = []
    for day in DAYS:
        exs = []
        for ex in state["plan"].get(day, []):
            last = state["last"].get(ex["name"]) or {}
            if last.get("sets"):
                item = {"exercise": ex["name"], "weight_kg": last["weight_kg"], "sets": last["sets"]}
            else:
                item = {"exercise": ex["name"], "sets": ex["sets_count"]}
            if ex.get("target_reps"):
                item["target_reps"] = ex["target_reps"]
            if ex.get("drop_set"):
                item["drop_set"] = True
            exs.append(item)
        workouts.append({"day_type": day,
                         "status": "completed" if any(h["day_type"] == day for h in state["history"]) else "template",
                         "exercises": exs})
    return {"exported_at": datetime.now(timezone.utc).isoformat(),
            "workouts": workouts, "history": state["history"]}


def state_from_import(data: dict) -> dict:
    if isinstance(data.get("state"), dict) and "plan" in data["state"]:
        return migrate_state(data["state"])
    if data.get("workouts"):
        s = seed_state(data)
        s["history"] = data.get("history", [])
        return migrate_state(s)
    raise ValueError("Unrecognised backup format")


# ---------- persistence ----------
def save_state(state: dict) -> None:
    tmp = PROGRESS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(PROGRESS_FILE)


def load_state() -> dict:
    if PROGRESS_FILE.exists():
        try:
            s = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
            if "plan" in s and "last" in s:
                return apply_first_use_baseline(migrate_state(s), seed_state(load_seed()))
        except (json.JSONDecodeError, OSError):
            pass
    s = seed_state(load_seed())
    save_state(s)
    return s


if "store" not in st.session_state:
    st.session_state.store = load_state()
store = st.session_state.store
active = store.get("active")

# ---------- header ----------
st.title("🏋️ Iron Log")
done_sessions = len(store["history"])
st.caption(f"{datetime.now().strftime('%a %d %b')} · Push / Pull / Legs · "
           f"{done_sessions} session{'s' if done_sessions != 1 else ''} logged")
view = st.radio("View", ["Train", "History", "Data"], horizontal=True,
                label_visibility="collapsed")

# ---------- TRAIN: pick a day & start ----------
if view == "Train" and not active:
    upcoming = next_day(store["history"])
    st.caption("Baseline: workout_splits.json (first use) — your logged workouts take over once you finish a session."
               if not store["history"] else
               "Baseline: your logged workouts (most recent session per exercise).")
    st.success(f"**Up next: {upcoming.capitalize()} day** "
               f"({'last: ' + store['history'][0]['day_type'].capitalize() + ' ' + store['history'][0]['date'][:10] if store['history'] else 'start of the rotation — your Pull weights are already loaded'})")
    day = st.radio("Workout day", DAYS, index=DAYS.index(upcoming),
                   format_func=str.capitalize, horizontal=True)
    for i, ex in enumerate(store["plan"][day], 1):
        last = store["last"].get(ex["name"]) or {}
        kind, msg = suggestion_for(store, ex["name"])
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            c1.markdown(f"**{i}. {ex['name']}**" + ("  · drop set" if ex["drop_set"] else ""))
            if last.get("sets"):
                c1.caption(f"Last: {last['weight_kg']} kg × {', '.join(map(str, last['sets']))}")
            elif ex["target_reps"]:
                c1.caption(f"Target: {ex['target_reps']} reps · {ex['sets_count']} sets · no weight logged yet")
            (c1.warning if kind == "weight" else c1.info)(msg)
            c2.link_button("▶ Form", yt_url(ex["name"]), use_container_width=True)
    st.info("**Starting point:** every exercise is pre-filled with exactly what "
            "you did last time — same weight, same reps per set — so you only "
            "edit what changed. **Progression:** aim +1 rep per set; hit the "
            "top of the rep range on every set and you'll be flagged to add "
            "+2.5 kg (a suggestion — the pre-fill still starts at last time).")
    if st.button(f"Start {day.capitalize()} workout", type="primary", use_container_width=True):
        store["active"] = start_session(store, day)
        save_state(store)
        st.rerun()

# ---------- ACTIVE SESSION: log set by set ----------
if view == "Train" and active:
    for ex in active["exercises"]:
        ex.setdefault("logged", [{"reps": r, "done": False} for r in ex["targets"]])
    total = sum(len(e["logged"]) for e in active["exercises"])
    done_n = sum(s["done"] for e in active["exercises"] for s in e["logged"])
    st.subheader(f"{active['day_type'].capitalize()} day — in progress")
    st.progress(done_n / total if total else 0, text=f"{done_n} / {total} sets done")
    idx = int(active.get("current", 0))
    names = [e["name"] for e in active["exercises"]]
    idx = st.selectbox("Exercise", range(len(names)), index=idx,
                       format_func=lambda i: f"{i + 1}. {names[i]}", key="exercise_picker")
    active["current"] = idx
    ex = active["exercises"][idx]
    kind, msg = suggestion_for(store, ex["name"])
    (st.warning if kind == "weight" else st.info)(msg)
    st.markdown(f"### {ex['name']}")
    st.link_button("▶ Watch form on YouTube", yt_url(ex["name"]))
    if ex.get("drop_set"):
        st.caption("Drop set: on the last set, drop the weight and keep going.")
    ex["weight_kg"] = st.number_input("Weight (kg)", min_value=0.0, step=WEIGHT_STEP,
                                      value=float(ex["weight_kg"]), key=f"weight_{idx}")
    for j, s in enumerate(ex["logged"]):
        c1, c2 = st.columns([3, 1])
        s["reps"] = c1.number_input(f"Set {j + 1} reps", min_value=0, step=1,
                                     value=int(s["reps"]), key=f"reps_{idx}_{j}")
        s["done"] = c2.checkbox("Done", value=bool(s["done"]), key=f"done_{idx}_{j}")
    b1, b2 = st.columns(2)
    if b1.button("＋ Set", use_container_width=True, key="add_set"):
        ex["logged"].append({"reps": ex["logged"][-1]["reps"] if ex["logged"] else 10, "done": False})
        save_state(store); st.rerun()
    if b2.button("－ Set", use_container_width=True, key="remove_set") and len(ex["logged"]) > 1:
        ex["logged"].pop(); save_state(store); st.rerun()
    t1, t2, t3 = st.columns(3)
    for col, secs in ((t1, 60), (t2, 90), (t3, 120)):
        if col.button(f"Rest {secs}s", use_container_width=True, key=f"rest{secs}"):
            st.session_state.rest_end = time.time() + secs; st.rerun()
    if st.session_state.get("rest_end"):
        # Auto-refreshing countdown: client-side JS, no manual refresh needed.
        if time.time() < st.session_state.rest_end:
            components.html(rest_timer_html(int(st.session_state.rest_end * 1000)), height=110)
            if st.button("Stop timer", key="rest_stop"):
                st.session_state.rest_end = None; st.rerun()
        else:
            components.html(rest_timer_html(int(st.session_state.rest_end * 1000)), height=110)
    save_state(store)  # draft persists on every interaction — safe to close the app
    nav1, nav2 = st.columns(2)
    if nav1.button("← Prev exercise", use_container_width=True, disabled=idx == 0, key="prev_ex"):
        active["current"] = idx - 1; save_state(store); st.rerun()
    if nav2.button("Next exercise →", use_container_width=True, disabled=idx == len(names) - 1, key="next_ex"):
        active["current"] = idx + 1; save_state(store); st.rerun()
    with st.expander("All exercises in this workout"):
        for i, e in enumerate(active["exercises"]):
            d = sum(s["done"] for s in e["logged"])
            st.write(f"{i + 1}. {e['name']} — {d}/{len(e['logged'])} sets"
                     + (" · now" if i == idx else ""))
    f1, f2 = st.columns(2)
    if f1.button("Discard workout", use_container_width=True, key="discard"):
        store["active"] = None; save_state(store); st.rerun()
    if f2.button("Finish & save ✓", type="primary", use_container_width=True, key="finish"):
        logged = [{"exercise": e["name"], "weight_kg": float(e["weight_kg"]),
                   "target_reps": e.get("target_reps"), "drop_set": e.get("drop_set"),
                   "sets": [int(s["reps"]) for s in e["logged"] if s["done"]]}
                  for e in active["exercises"]]
        try:
            entry = finish_session(store, active, logged)
            save_state(store)
            st.success(f"{entry['day_type'].capitalize()} saved ✓ Next up: {next_day(store['history']).capitalize()}")
            st.balloons(); st.rerun()
        except ValueError as err:
            st.error(str(err))

# ---------- HISTORY ----------
if view == "History":
    if not store["history"]:
        st.info("No sessions saved in the app yet. Your Pull results from "
                "workout_splits.json are loaded as starting weights — finish "
                "your first in-app workout and it will appear here.")
    total_sets = sum(len(e["sets"]) for h in store["history"] for e in h["exercises"])
    volume = sum(r * (e["weight_kg"] or 0) for h in store["history"]
                 for e in h["exercises"] for r in e["sets"])
    m1, m2 = st.columns(2)
    m1.metric("Sessions", len(store["history"]))
    m2.metric("Total volume", f"{volume:,.0f} kg", f"{total_sets} sets")
    for h in store["history"]:
        with st.container(border=True):
            st.markdown(f"**{h['day_type'].capitalize()} · {h['date'][:10]}**")
            for e in h["exercises"]:
                st.write(f"{e['exercise']} — **{e['weight_kg']} kg × {', '.join(map(str, e['sets']))}**")
            if st.button("Delete this session", key=f"del_{h['id']}"):
                store["history"] = [x for x in store["history"] if x["id"] != h["id"]]
                save_state(store); st.rerun()

# ---------- DATA: backup / restore / reset ----------
if view == "Data":
    st.subheader("Your data")
    st.write("Progress auto-saves to `progress.json` next to the app as you train. "
             "On Streamlit Cloud that file resets if the app reboots, so export a "
             "backup after a session — it takes two seconds and works everywhere.")
    st.download_button("⬇ Export JSON backup (workout_splits.json format)",
                       json.dumps(export_payload(store), indent=2),
                       file_name="workout_splits.json", mime="application/json",
                       use_container_width=True)
    up = st.file_uploader("Import a backup", type=["json"])
    if up is not None and st.button("Restore from this file", use_container_width=True):
        try:
            st.session_state.store = state_from_import(json.loads(up.read().decode("utf-8")))
            save_state(st.session_state.store)
            st.success("Import complete ✓"); st.rerun()
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as err:
            st.error(f"Import failed: {err}")
    if st.button("Reset to original plan (workout_splits.json)", use_container_width=True):
        st.session_state.store = seed_state(load_seed())
        save_state(st.session_state.store)
        st.success("Reset — Pull starting weights restored."); st.rerun()
