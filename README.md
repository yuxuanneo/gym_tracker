# Iron Log — Workout Tracker

A phone-first Push / Pull / Legs tracker. No account, no cost.
The **Streamlit app (`app.py`) is the main app**; the static PWA
(`index.html`) is kept as an offline reference version.

## Run the Streamlit app

```bash
cd gym_tracker
streamlit run app.py            # already installed, or: pip install -r requirements.txt
```

Open the URL it prints (usually http://localhost:8501). At the gym on the
same Wi-Fi, run `streamlit run app.py --server.address 0.0.0.0` and open
`http://<your-computer-ip>:8501` on your phone.

In the app: pick Push / Pull / Legs → **Start workout** → log each set with
the −/+ steppers → **Done** per set → **Rest 90s** between sets →
**Finish & save**. Every exercise has a **▶ Form** YouTube tutorial link.
Every exercise starts pre-filled with exactly what you did last time —
same weight, same reps — so you only edit what changed. The app suggests
+1 rep per set, and flags +2.5 kg once you hit the top of a rep range on
every set, but it never changes your starting numbers for you. The rest
timer (60/90/120s) counts down on its own and beeps/vibrates at zero.

**First use vs. later:** until you finish your first session, the plan and
starting weights/reps are re-read from `workout_splits.json` on load, so
edits to that file still take effect. From your first finished session on,
your logged workouts are the baseline and the JSON is never re-applied.

**Memory:** progress auto-saves to `progress.json` beside the app (drafts
included, so closing mid-workout is safe). On Streamlit Cloud that file
resets when the app reboots, so use **Data → Export JSON backup** after a
session and **Import** to restore — the backup matches `workout_splits.json`.

## Put it on your phone free (Streamlit Community Cloud)

1. Push this folder to a GitHub repo (see the git commands in the PWA section below — same repo works).
2. Go to [share.streamlit.io](https://share.streamlit.io) → sign in with GitHub → **New app** → pick the repo, branch `main`, main file `app.py` → **Deploy**. No cost, no AWS.
3. Open the `*.streamlit.app` URL on your phone → browser menu → **Add to Home Screen**. It opens like a normal app.

Note: free Community Cloud apps sleep when idle and take ~30s to wake on
first open, and their local file storage is ephemeral — that's why the
Export/Import backup in the Data tab matters.

## PWA reference version (offline, GitHub Pages)

The static version below needs no Python and works fully offline once
installed; it stores data in the phone browser instead of `progress.json`.

## Your starting data

Seeded from `workout_splits.json`:

| Day | Status | What's loaded |
|---|---|---|
| Push | Template | 7 exercises with target rep ranges (e.g. Bench 5–8) |
| Pull | Completed | Your real weights — Lat Pulldown 50 kg × 9,9,9,9, Row 36 kg × 10s, etc. |
| Legs | Template | 6 exercises with target rep ranges |

## How a gym session works

1. Open the app — it tells you what's **up next** in the Push → Pull → Legs rotation.
2. Tap **Start workout**. One exercise at a time, big tap targets.
3. For each set: tap **− / +** if your reps differ from the target, then tap **Done**.
   A 90-second rest timer starts automatically (60 / 90 / 120s options, vibrates when done).
4. Adjust weight with **− / +** (2.5 kg steps, plus ±1 / ±5 shortcuts) or type it.
5. Tap **▶ Form** on any exercise any time for a YouTube form tutorial.
6. **Finish & save** — your new weights/reps become next session's starting point.

**Progressive overload, built in:** every session pre-fills *exactly what
you did last time* — same weight, same reps per set. Aim for +1 rep per
set; when you hit the top of a rep range on every set it flags **+2.5 kg**
as a suggestion. You just confirm what you actually did.

If you close the app mid-workout, it resumes exactly where you left off.

## Put it on your phone (free, ~2 minutes)

This is a static site, so GitHub Pages hosts it for free — no Streamlit, no AWS.

```bash
cd gym_tracker
git init && git add . && git commit -m "Iron Log workout tracker"
git branch -M main
git remote add origin https://github.com/<your-username>/gym_tracker.git
git push -u origin main
```

Then on GitHub: **Settings → Pages → Build and deployment → Source: Deploy from a branch → `main` / `(root)` → Save.**

Open the Pages URL on your phone, then:

- **iPhone:** Share → *Add to Home Screen*
- **Android:** ⋮ menu → *Add to Home screen / Install app*

It now opens full-screen like a native app and works offline.

> Why not just commit data back to the repo from the app? A static page can't
> write to GitHub without a token in the page (unsafe). Instead the app saves
> on-device and **Data → Export JSON** downloads an updated `workout_splits.json`
> any time you want a backup or want to commit your progress.

## Files

| File | Purpose |
|---|---|
| `index.html` | The whole app (open it directly to try it locally) |
| `workout_splits.json` | Your plan + starting weights (also the export format) |
| `manifest.webmanifest`, `sw.js`, `icon.svg` | Makes it installable + offline on your phone |

## Backup / move to a new phone

**Data tab → Export JSON backup**, then **Import JSON backup** on the new device.
It accepts both app backups and a plain `workout_splits.json`.

## Automatic private cloud backup (Supabase, ~5 minutes, free)

Browser storage alone is *best-effort* — it can be evicted by the OS/browser
without you clearing anything, and it dies with the phone. Supabase sync keeps
an automatic private copy in the cloud. Nobody else can read it: the table has
Row Level Security, so each account only ever sees its own row.

1. Create a free project at [supabase.com](https://supabase.com) (any name/region).
2. In the project: **SQL Editor → New query**, paste the contents of
   `supabase_schema.sql` from this repo, **Run**.
3. **Project Settings → API**: copy the **Project URL** and the **anon /
   publishable key**. (Never use the `service_role` key in the app.)
4. In the app: **Data tab → ☁ Private cloud backup** — paste URL + key + your
   email → **Save Supabase settings** → **Email me a sign-in link**.
5. Open the email **on the phone**. In the home-screen app, prefer the 6-digit
   code path (**Verify code**) if your email shows a code — iOS keeps Safari
   and home-screen app storage separate, so a link tap can sign in the wrong
   container. (If you only get a link, sign in once in the browser tab you
   installed from, then use the app.)
6. Back in the app tap **Sync now** once. After that, every change auto-syncs
   in the background whenever you're online and signed in. **Restore from
   cloud** brings it back on a new phone (it asks before overwriting).

Good to know: local logging never waits for the cloud — offline at the gym,
everything saves on-device and syncs next time you're online. Free Supabase
projects pause after about a week of inactivity; if a sync fails after a
long break, open the Supabase dashboard to resume the project, then Sync now.
Your session stays signed in on the device until you sign out.
