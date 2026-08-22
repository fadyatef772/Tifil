# Tifl · طِفل — Adaptive Learning for Children with Down Syndrome

A web-first learning app for children with Down syndrome. A child works through
short, patient exercises tuned to their level; an adult (parent or therapist)
watches progress and stays in the loop. Bilingual Arabic / English.

> This is an MVP foundation, built web-first. A mobile wrapper (PWA, Flutter, or
> React Native) can sit on the same API next.

---

## Why it's built this way

**Two interfaces, one engine.** The child is the direct user, but a child with
Down syndrome can't self-report whether learning is really happening — clicks
and time-on-task lie. So every child-facing session feeds an **adult dashboard**
that makes real progress legible and keeps a human in charge of the goals.

**The adaptive engine is rule-based, not a black box.** It uses *mastery-based
progression*: a child moves up a level only after answering most of a recent
window correctly, and moves down only after a sustained struggle — never below
level 1. An adult can read a child's history and see exactly *why* the app
promoted or demoted them. At this data scale a neural recommender would overfit
and, worse, couldn't explain itself. (Room to add ML later: cross-child exercise
recommendation once there's real data — see `adaptive_engine.py`.)

**No punishment.** A wrong answer wiggles the card and says "try again" — the
same exercise is simply offered again. Failure never removes progress within a
session; it only slows promotion.

**Design for the child's real needs.** One task on screen at a time; big touch
targets; image-and-audio first (prompts are read aloud via the browser's speech
synthesis); consistent, predictable structure; immediate positive reinforcement.

---

## Architecture

```
Child interface ─┐                        ┌─ Adult dashboard
(big cards,      │                        │  (progress, levels,
 audio, no       ├──►  FastAPI  ──►  Adaptive engine  ──►  Data store    goals, sessions)
 punishment,     │     (REST)        (mastery logic,       (SQLite →
 optional mic,   │                    interpretable,         Supabase)
 session stars)  │                    goal-weighted)
                 │                         ▲       ▲
                 │        nudges exercise choice    reads Mastery/Attempt,
                 │        only, never Mastery ───┐  flips Goal.status
                 │                    ML struggle │  (app/services/goals.py)
                 │                    predictor   │
                 │            (proof of concept,  │
                 │           synthetic-trained) ──┘
                 └──► Whisper speech transcriber (local, optional, has a
                       stub fallback) ──► fuzzy match ──► same engine above
Both feed one engine and one store ──────┘
```

```
backend/
  app/
    core/        config (engine + ML + speech + sessions/goals tunables) · database
    domain/      models (ORM: Parent, Child, ... Session, Goal, LevelUpEvent) · schemas (API contract)
    services/    adaptive_engine.py   ← the pedagogical core (goal-weighting
                 goals.py                added, see below — level logic itself
                 rewards.py              is unchanged; rewards ride alongside)
                 daily_routine.py     ← read-only daily streak / today's plan
                                        / activity calendar (derived from
                                        Attempt timestamps — see "Daily
                                        Routine"; the rewards streak is
                                        untouched)
                 parent_view.py      ← read-only parent rollups + gentle,
                                        rule-based home-activity suggestions
                                        (never a diagnosis — see "Parent View")
                 exercise_types/     ← pluggable exercise-type system, see below
    ml/          struggle_predictor.py  ← ML layer, see below
                 synthetic_data.py, features.py, intervention.py
                 train_struggle_predictor.py, evaluate_struggle_predictor.py
                 artifacts/struggle_predictor.joblib  ← trained artifact
    speech/      transcriber.py (Whisper/stub), match.py  ← DL layer, see below
    api/         routes.py            ← thin HTTP layer
                 auth.py              ← parent authentication (signup, login, me)
    seed.py      bilingual starter curriculum
    main.py      FastAPI entrypoint
  verify.py           end-to-end check of the core learning loop
  verify_auth.py      end-to-end check of parent authentication (12 checks)
  link_orphan_children.py  one-time migration: links pre-auth orphaned children
                       to a parent (idempotent, safe on existing data)
  verify_sessions.py  end-to-end check of sessions + goals
  verify_rewards.py   end-to-end check of stars + streak + avatar unlocks
  verify_exercise_types.py  end-to-end check of the pluggable exercise types
  verify_journey.py   end-to-end check of the child's learning-journey path
  verify_parent_view.py end-to-end check of the parent view (read-only
                     rollups + gentle suggestions, see below)
  verify_daily_routine.py end-to-end check of the daily routine (streak,
                      today's plan, calendar — derived, read-only)
  verify_speech_matching.py deterministic check of the Arabic speech
                      normalization + fuzzy-matching pipeline (no audio)
  verify_ml.py        deterministic check that the struggle-predictor
                      pipeline works (artifact loads, features compute,
                      predictions directionally sensible) — tests the
                      plumbing, NOT clinical accuracy (the model is a
                      proof-of-concept trained on simulated data)
  verify_answers.py   shared "what a correct/wrong answer looks like" helper
frontend/
  src/
    auth/        AuthContext · LoginScreen · SignupScreen
    child/       ChildHome → LearningJourney → ExercisePlayer (tap or
                 optional mic, session stars)  exercises/  registry.tsx +
                 Choice/Matching/Sequencing/Tracing
    adult/       Dashboard (progress, goals, recent sessions) ·
                 ParentView (plain-language summaries + home ideas)
    api.ts · i18n.ts (strings + speech) · types.ts · App.tsx
```

---

## Run it

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# REQUIRED: generate a secret key for bearer token signing.
# The app will not start without TIFL_SECRET_KEY.
export TIFL_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

python -m app.seed --reset          # create + seed the database
python -m app.ml.train_struggle_predictor   # optional: retrain the ML layer
                                             # (a trained artifact ships in
                                             # app/ml/artifacts/ already)
uvicorn app.main:app --reload --port 8000
# API docs at http://localhost:8000/docs
```

You can also put `TIFL_SECRET_KEY` in a `.env` file (see `.env.example` for a
template). The app checks at startup that the key is set and is not the old
insecure dev default — it will refuse to start with a clear error message if
either check fails.

The speech endpoint works with no extra setup — it downloads Whisper's
weights on first real use (see "Deep Learning layer" below) or falls back
to a stub if it can't.

Verify the whole adaptive loop end to end (creates a child, answers exercises,
confirms level-ups fire, checks progress):

```bash
python verify.py
```

Verify parent authentication end to end (signup, login, me, child creation with
auto parent_id, scoped child list, cross-parent access denied, unauthenticated
denied, password minimum length, duplicate email rejected, invalid token
rejected — 10 checks):

```bash
python verify_auth.py
```

Verify sessions + goals end to end (starts a session, plays it to its
target, ends it and checks the summary, creates both kinds of goal, drives
each to "achieved"):

```bash
python verify_sessions.py
```

Verify rewards end to end (stars accumulate on correct answers, a wrong
answer resets the streak but never costs a star, and accumulating stars
unlocks the next avatar):

```bash
python verify_rewards.py
```

Verify the pluggable exercise-type system end to end (proves each of the
new types — matching, sequencing, tracing — serializes without leaking its
answer, a correct structured answer flows into mastery *and* rewards, and a
wrong answer fails gently with no punishment; also re-checks the legacy
`choice` path):

```bash
python verify_exercise_types.py
```

Verify the child's learning-journey projection end to end (a new child's
first skill is "current" with the rest "locked"; an adult-set active goal
moves the focus to that skill; mastering a skill through the real API flips
it to "mastered" and advances the path; archiving the goal returns the focus
to the first non-mastered stop; and journey reads never write anything):

```bash
python verify_journey.py
```

Verify the parent view end to end (builds a known history for one child —
a today batch, a 3-days-ago batch, an 8-days-ago batch — then asserts the
today vs this-week rollup numbers match it exactly, that the gentle
suggestions follow the documented rules, and that reading the parent view
never writes anything):

```bash
python verify_parent_view.py
```

Verify the daily routine end to end (mocks attempt timestamps across
several days through the real answer flow, then asserts the daily streak
increments on consecutive days, stays "alive" while the run ends yesterday,
never inflates on same-day repeats, resets gently after a missed day, the
today's-plan progress is exact, and the daily reads never write):

```bash
python verify_daily_routine.py
```

Verify the speech answer-**matching** pipeline deterministically (no audio
needed — this tests the normalization + fuzzy-matching that runs *after*
transcription): Arabic tashkeel/kashida stripping, alef/ta-marbuta/maqsura
folds and the new ؤ→و, ئ→ي, لا-ligature folds are applied to **both** the
transcript and the expected label, and the matcher turns messy transcripts —
including the real outputs observed from Whisper (`أحمرو`, `أهماعوا`,
`أزرقه`, `أفضل`) — into a confident match on the real option or an honest
"unclear", never a guess:

```bash
python verify_speech_matching.py
```

Verify the ML struggle predictor deterministically (no retraining, no
database): the shipped artifact loads and has the expected shape,
`extract_features` computes exact expected values from small hand-built
histories (level filtering, trend sign, the 10-attempt window), and
predictions on two clear-cut synthetic patterns lean the sensible direction —
the struggling pattern scores a higher P(struggling) than the doing-well one.
**This validates the pipeline plumbing (artifact loads, features compute,
predictions are directionally sensible), NOT clinical accuracy** — the model
is a proof-of-concept trained on simulated data (see "Machine Learning layer"
below):

```bash
python verify_ml.py
```

The verify scripts use a throwaway SQLite file each, so they never touch a
real database.

### Frontend

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173  (proxies /api to :8000)
```

Open the app, use the top-right toggle to switch **child mode** / **parent
view**, and the language button to switch **عربي / English**. In child mode,
tapping a child's card opens their **learning path** (`LearningJourney`):
one linear, child-friendly path of skills ordered as in the seed curriculum —
mastered stops in colour, the single active "current" stop glowing (and
marked with 🎯 when an adult set an active goal on it), and locked ones ahead
dimmed as silhouettes. Tapping the current stop starts `ExercisePlayer`;
finishing a session (or leaving mid-session) returns to the path, which
re-fetches so any new mastery/stars appear immediately, and the path's back
arrow returns to the child picker.

---

## Pluggable exercise types

The MVP shipped a single exercise shape (tap the right card). This iteration
turns that into a **pluggable type system**: the adaptive engine, the
goal/reward code, and the ML struggle predictor only ever consume
`is_correct` — they don't care *how* an answer was produced — so a new
exercise type is now just **one backend module + one registration + one
frontend component + one registration**, with zero changes to the engine,
routes, or the other types.

**Backend contract** (`app/services/exercise_types/`): each type is a small
module with a `key` and two pure functions:

- `serialize_for_child(exercise)` — the child-facing payload, with every
  answer-bearing key stripped (the answer never leaves the server);
- `validate(exercise, payload)` — decide `is_correct` from the submitted
  structured `answer`.

A registry (`__init__.py`) maps `exercise.type` → module; the API layer
calls `serialize_for_child` when serving an exercise and `validate` when an
answer arrives. Adding a type touches only that package. Speech answers
remain choice-only (the endpoint 400s on any other type).

The four types today:

| type | what the child does | payload served | answer submitted |
|---|---|---|---|
| `choice` | tap the right card | `{options: [...]}` | `{option_id}` (legacy) or `{answer: {option_id}}` |
| `matching` | tap left, tap its right partner (2–3 pairs) | `{pairs: [{id, left, right}]}` | `{answer: {pairings: {left_id: right_id}}}` |
| `sequencing` | tap steps in the correct order (3 steps, shuffled) | `{items: [...]}` (step numbers stripped) | `{answer: {order: [ids]}}` |
| `tracing` | finger-traces a guide glyph | `{glyph, visual, guide: [{x,y}]}` (0..100 space) | `{answer: {points: [{x,y}]}}` |

A wrong structured answer behaves exactly like a wrong tap: `is_correct:
false`, `feedback: "try_again"`, no star lost, streak quietly reset — the
no-punishment rule holds across every type.

**Tracing is motor practice, not handwriting recognition.** There is no OCR
and no shape classifier. The validator runs a deliberately lenient
*coverage* check: it resamples the trace, and the exercise passes when at
least `tracing_coverage_threshold` (default 0.6) of the guide's sample
points lie within `tracing_proximity_radius` (default 18) of some traced
point (all tunables in `app/core/config.py`). A child who wanders near the
shape and covers enough of it passes — that is the intent (celebrate the
motor effort), and it is exactly why the code and this README call it a
coverage check and **not** recognition. A real handwriting-recognition
engine is a separate, future feature.

**Frontend contract** (`frontend/src/child/exercises/`): `ExercisePlayer`
never switches on the type directly. It renders `registry.tsx`, which maps
`exercise.type` → component (`ChoiceExercise`, `MatchingExercise`,
`SequencingExercise`, `TracingExercise`). Each component gets the exercise,
the language, a `disabled` flag (locked once answered correctly) and an
`onSubmit(answer)` callback that posts the structured answer and resolves
with the engine's verdict so the renderer can show type-appropriate
"try again" feedback. Choice's card grid was extracted byte-for-byte from
the old player; the other three are tap-first, one task per screen, big
touch targets.

**Seed.** `seed()` is level-granular and idempotent: it adds any newly
defined level/skill to an existing database without touching what's there,
so re-running it against a real `tifl.db` grew the curriculum from 9 to 14
skills and 58 to 83 exercises with no migration and no data loss. The
curriculum now spans three categories — `cognitive`, `daily_life`, and
`social` — across the four exercise types (see "Curriculum content" below).
New-type exercises store `correct_option_id = "n/a"` (a non-nullable column
predating the pluggable system; the real truth lives inside each type's
`options`).

---

## Curriculum content and content caveats

The starter curriculum has **14 skills in three categories**, bilingual
ar/en, across the four exercise types. Levels and exercise counts per skill
(24 levels, 83 exercises total):

| category | skill | levels | exercises |
|---|---|---|---|
| `cognitive` | Colors (colors) | 3 | 8 |
| `cognitive` | Numbers (numbers) | 3 | 7 |
| `daily_life` | Washing hands (handwashing) | 3 | 6 |
| `daily_life` | Getting dressed (dressing) | 3 | 4 |
| `cognitive` | Shapes (shapes) | 3 | 8 |
| `cognitive` | Animals (animals) | 3 | 7 |
| `cognitive` | Feelings (emotions) | 3 | 7 |
| `daily_life` | Our body (body_parts) | 2 | 6 |
| `daily_life` | Morning routine (morning_routine) | 3 | 5 |
| `social` | Greetings (greetings) | 2 | 5 |
| `social` | Taking turns (turn_taking) | 2 | 4 |
| `cognitive` | Picture memory (memory_pairs) | 2 | 4 |
| `cognitive` | Let's remember (recall) | 2 | 6 |
| `cognitive` | Picture naming (picture_naming) | 2 | 6 |

The three `social`-category skills are new: **Greetings** (say hi / good
morning / bye — matching or choosing the right greeting for the situation),
**Taking turns** (order the 3-step routine of asking → waiting → receiving),
and the two memory skills sit in `cognitive`: **Picture memory** (flip and
match pairs) and **Let's remember** (see three items, then choose which one
was there) — all implemented with the existing pluggable types.

**Content caveats (read before extending):**

- **`emotions` is basic recognition, not assessment.** It is face-to-word
  recognition of happy/sad/angry/scared emojis (choice + matching) only. It
  never draws any conclusion about a child's feelings or wellbeing. Emotion
  content should be reviewed by a specialist (psychologist or
  special-education therapist) before use.
- **`picture_naming` is word recognition, not speech therapy.** The child
  sees an emoji and picks (or optionally says) the matching written word.
  Real speech and pronunciation practice must be designed with a speech
  therapist. The optional 🎤 button reuses the existing choice speech-answer
  flow unchanged — incidental, not a claim of speech training.
- **`turn_taking` is sequencing, not social evaluation.** It teaches a
  3-step routine by ordering only; it never judges a child's social
  behavior.

---

## Machine Learning layer: struggle predictor

**Status: proof of concept, trained entirely on synthetic data.** The app
has no real users yet, so there is no real attempt history to learn from.
`app/ml/synthetic_data.py` simulates four plausible child archetypes (fast
learner, average, struggler, inconsistent) and generates thousands of
(features, label) examples from them; `train_struggle_predictor.py` fits a
`RandomForestClassifier` on that alone. **This is explicitly not a claim
that the model has been validated on real children** — see the module
docstrings in `app/ml/` for the full reasoning, and retrain on real,
consented attempt logs before using this in production.

Four interpretable features per (child, skill, current level): recent
accuracy, average tries, a short-term trend, and attempts logged at the
current level (`app/ml/features.py`). The label mirrors the rule-based
engine's own demotion rule (`struggle_window` / `struggle_correct` in
`app/core/config.py`) but looks ahead, so the model's job is to raise the
same flag *earlier* than the rule engine's window would fill.

```bash
cd backend
python -m app.ml.train_struggle_predictor      # generates data, trains, saves the model
python -m app.ml.evaluate_struggle_predictor   # scores it against a FRESH, unseen synthetic set
python verify_ml.py                            # plumbing check of the shipped artifact (no retraining)
```

A trained artifact is committed at `app/ml/artifacts/struggle_predictor.joblib`
(regenerate any time with the command above; training is deterministic,
seeded, and takes a few seconds). Measured on a held-out synthetic set
(different random seed from training, `evaluate_struggle_predictor.py`):
accuracy 0.760, precision 0.407, recall 0.756 on the "struggling" class
(imbalanced classes, ~18% struggling — recall matters more here since a
missed struggle costs a harder few minutes, while a false positive just
serves an easy warm-up rep).

**How it's wired in, safely:** `GET /api/children/{id}/next-exercise` still
calls the untouched rule-based engine first to pick a skill and level. Only
then is the ML signal consulted — if it's confidently "struggling", the
*same-turn* exercise is swapped for one at a level the child has already
passed (a confidence-building rep), never touching the Mastery row, and the
response's `struggle_signal` field reports what happened. If the model
can't load, or feature extraction/inference fails for any reason, the
signal reports `model_available: false` and nothing changes — the
rule-based engine's own choice is always the fallback. A direct inspection
endpoint also exists: `GET /api/children/{id}/skills/{skill_id}/struggle-prediction`.

---

## Deep Learning layer: speech answers

Lets a child speak an answer instead of tapping, using
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) (Whisper via
CTranslate2) running locally — no audio ever leaves the machine.

```
POST /api/speech-answer   (multipart form: child_id, exercise_id, tries,
                            lang, audio file)
```

The audio is transcribed, the transcript is fuzzy-matched (ar/en aware —
Arabic diacritics and letter-shape variants are folded before comparing) against
the exercise's option labels (`speech_match_threshold` in config, default 0.55),
and a confident match is recorded through the *exact same* `record_answer` the
tap flow uses. A transcript that matches nothing well enough is reported as
`feedback: "unclear"` and is **not** logged as an attempt — an unintelligible
recording can't count against the child, consistent with the app's
no-punishment design.

**The answer language is pinned, never auto-detected.** The exercise/child
language is sent with the request (the frontend uses the child's
`preferred_language`, not the adult's UI toggle), and `transcribe()` requires an
explicit `"ar"`/`"en"` — auto-detection is dramatically worse for short Arabic
words (measured: they came back as Latin/Cyrillic gibberish).

**Arabic fixes that actually work** (measured on identical audio, real Arabic
speech → the live endpoint, correct answer "أحمر" for a colors exercise):

| config | transcript | match |
|---|---|---|
| old default (`base`, no vocabulary hint) | `أهما رو` | **0.55 → "unclear" (correct answer rejected)** |
| new default (`small` + vocabulary hint) | `أحمر` | **1.00 → correct** |

Three things fixed this:

1. **Bigger model.** The default Whisper model is now `"small"` (~460MB) — the
   accuracy/speed sweet spot for an offline family PC and a much better fit
   for Arabic than `tiny`/`base`. A stronger machine can opt into `"medium"`
   (~1.5GB, better Arabic still, but ~3x the download and noticeably slower on
   CPU) with `TIFL_WHISPER_MODEL_SIZE=medium` — no code change.
2. **Vocabulary biasing.** The endpoint builds a Whisper `initial_prompt` from
   the current exercise's option labels in the answer language, so decoding is
   biased toward the actual choices; `beam_size` rose from 1 to 3. This alone
   lifted `base` to exact on the same audio.
3. **Stronger Arabic normalization.** `app/speech/match.py` now also folds
   ؤ→و and ئ→ي (hamza-on-waw/yeh) and every lam-alef ligature form (ﻻ→لا) on
   top of the existing tashkeel/kashida stripping and أ/إ/آ→ا, ة→ه, ى→ي folds —
   applied identically to the transcript and the expected label.

**Model weights are not bundled.** The first time transcription is actually
needed, faster-whisper downloads the model (default `"small"`, ~460MB) from
Hugging Face and caches it — after that it's fully offline. If a machine has
no internet on first run, or `faster-whisper` isn't installed, or
`TIFL_WHISPER_MODEL_SIZE` points at a model that fails to download, the
endpoint **does not crash or fake success** — it transparently falls back to a
stub transcriber that always returns an empty transcript (`feedback: "unclear"`,
`engine: "stub"`), so the request/response contract and the matching logic stay
testable even with zero internet. Set `TIFL_SPEECH_STUB=1` to force stub mode
(used by the backend's own tests so they never depend on a model download).

In the frontend, `ExercisePlayer` shows an additional 🎤 "say the answer"
button, feature-detected (`navigator.mediaDevices` + `MediaRecorder`) so it
simply doesn't render on a browser/context that lacks it. Tapping remains
the primary, always-available path.

---

## Sessions and Goals

**Sessions** give a play period a small, visible end instead of running
forever — short on purpose, matching a young child's attention span
(`session_exercise_target` in config, default 8 exercises).

```
POST /api/children/{id}/sessions/start   -> {session_id, target_exercises}
POST /api/sessions/{id}/end              -> summary (idempotent — ending an
                                             already-ended session just
                                             returns the same summary again)
GET  /api/sessions/{id}/summary          -> same summary shape, read-only
GET  /api/children/{id}/sessions         -> recent summaries, most recent
                                             first (powers the dashboard)
```

Every `Attempt` already had a nullable `session_id` column (unused until
now); `submit_answer` and `speech_answer` both pass it straight through to
`adaptive_engine.record_answer`, which was already storing it. A session
summary reports total attempts, accuracy, which skills were practiced, and
which level-ups happened — the last of those needed one small new table,
**`LevelUpEvent`** (child_id, session_id, skill_id, new_level), written by
`record_answer` at the exact moment it promotes a level. This was necessary
because `Mastery.updated_at` is touched on *every* answer, correct or not,
so it can't be used to reconstruct "did a level-up happen in this session"
after the fact — an event log was the honest way to make that queryable.

In `ExercisePlayer`, a row of stars (⭐/☆) shows progress toward the
session's target — visual, not a number, because that reads better to a
young child — and reaching the target replaces the endless "next exercise"
loop with a celebratory recap screen (attempts, accuracy per skill, any
level-ups) before returning to the child picker.

**Goals** let an adult set a target for one skill: either "practice this
skill" (no specific level) or "master up to level N". New table **`Goal`**
(child_id, skill_id, target_level nullable, status, created_at,
achieved_at).

```
POST  /api/children/{id}/goals   -> create (skill_id, optional target_level)
GET   /api/children/{id}/goals   -> list, newest first
PATCH /api/goals/{id}            -> update status (active/achieved/archived)
```

**How a goal affects exercise selection (and how it doesn't):**
`adaptive_engine.select_next_exercise` still does exactly what it did
before goals existed — rotate to the skill touched least recently, pick the
least-recently-seen exercise at the child's current level in it. The only
addition: if the child has an active goal, **with probability
`goal_bias_probability` (default 0.6)** the function instead tries the goal
skill(s) first, using that same least-recently-touched tie-break among just
them, before falling through to the unchanged full rotation if none of them
currently has anything to serve. This is a genuine weighting, not a hard
filter — a child with an active goal still sees their other skills roughly
40% of the time, and a child with *no* goals gets byte-identical behaviour
to before this feature existed (verified: `verify.py`, which never creates
a goal, still passes unchanged). The randomness is a single documented coin
flip per exercise selection, not hidden state, so the rule stays auditable
even though a single call's outcome isn't deterministic.

**How achievement is detected** (`app/services/goals.py`, called after
every recorded answer): a goal with a `target_level` is achieved once
`Mastery.highest_mastered >= target_level` — the rule-based engine's own
number, not a re-derived one. A level-less "practice" goal is achieved
after `goal_practice_attempts_target` (default 15) correct attempts on that
skill *since the goal was created* — attempts from before the goal existed
don't count. Neither path ever writes to Mastery or Attempt; this module
only reads them and flips `Goal.status`.

In the adult Dashboard, a new Goals section lets the adult pick a skill and
optional level, see each goal's status (active/achieved/archived) and
current progress, and archive one; a Recent Sessions section lists the last
few session summaries with their level-ups.

**Schema note:** both `Goal` and `LevelUpEvent` are brand-new tables, so
`Base.metadata.create_all()` (already called on every startup) creates them
automatically alongside the existing ones — verified by starting the app
against an existing `tifl.db` from before this feature and confirming both
tables appeared with no manual migration step. No existing table's columns
were changed, so no migration was needed for those.

---

## Learning Journey — the child's path

A child-facing view that turns raw progress into a single, legible path.
`GET /api/children/{id}/journey` is a **pure read-only projection** over
existing data — `Mastery`, `Goal`, `Skill`, `Rewards` — it never writes
anything and never consults the engine, rewards, ML or speech layers. Every
skill in the curriculum (ordered as seeded) becomes a **stop**, with a
derived status:

- **`mastered`** — `highest_mastered` reached the skill's level count;
- **`current`** — the single active focus: the skill an adult set an
  *active* goal on (reusing the goals data), if any isn't mastered yet;
  otherwise the first non-mastered stop in journey order;
- **`locked`** — every other non-mastered stop (upcoming, shown dimmed).

It also carries the child's total stars, so the path itself shows progress
without a separate call.

```
GET /api/children/{id}/journey
    -> { child_id, total_stars, stops: [{ skill_id, skill_key, name_ar,
         name_en, icon, category, total_levels, current_level,
         highest_mastered, status, is_active_goal }, ...] }
```

In `LearningJourney` (child mode), stops render as a linear path with a small
level pip per stop; the "current" stop glows and is the only one that starts
play. This is the child-facing entry point — `ChildHome` now opens the
journey on a child card tap, and tapping the current stop enters
`ExercisePlayer`. The stop emojis come from a small `icon`-key → emoji map in
the component that mirrors the seed's icon keys exactly (presentation only —
the data always comes from the API).

---

## Daily Routine — a gentle reason to come back each day

A small, cheerful daily-routine panel on the child's journey: a **daily
streak** (🔥 *N days*), a **today's plan** (filled stars toward a small fixed
target), and a simple **14-day activity calendar** (active days in colour,
inactive days merely pale). Fully bilingual ar/en.

**It builds healthy routine, NOT compulsion — the one governing principle.**
For a child with Down syndrome a missed day must never feel like a loss:

- A missed day resets the streak to 0 **gently**: the UI only ever frames a
  fresh start positively ("Let's start today!" / "يلا نبدأ النهارده!").
  There is no "you lost your streak", no "play or lose it" warning, no
  countdown, no guilt — anywhere in the backend or the frontend.
- The today's-plan target is small and fixed, and "done" counts *attempts*
  (the exact metric a session summary already uses for `target_reached`), so
  a child who is still learning still fills their stars — the plan can never
  become a source of anxiety.

**Derived, not stored — no new source of truth.** A child is *active* on a
UTC calendar day if they have at least one `Attempt` that day (from
`Attempt.created_at`; a session with zero attempts is not practice).
`app/services/daily_routine.py` is a pure read-only projection, exactly like
the journey and parent view: it never writes, never calls the engine, and
adds **no new table and no new column** — so `create_all` on an existing
`tifl.db` is a no-op and existing children's data is preserved untouched
(verified against the real database). The daily streak is **derived on every
read**, not stored.

**The daily streak is completely separate from the in-session rewards
streak.** The rewards layer's `streak` (consecutive correct *answers*,
`app/services/rewards.py`) is not read, written, or modified here — it stays
byte-for-byte as it was. Same-day repeat visits never inflate the daily
streak (a day is active or it isn't); they only advance today's plan.

```
GET /api/children/{id}/daily
    -> { child_id,
         daily_streak,            # consecutive active UTC days ending today
                                  # (or yesterday — the streak stays "alive"
                                  # until the day is over; a gap resets to 0)
         active_today,            # any attempt today
         today_plan: { target, done },   # target = settings.session_exercise_target
         recent_days: [ { date, active }, ... ] }  # last 14 days, oldest first
```

The streak logic in one line: count the consecutive active days ending today
(or, if today isn't played yet, ending yesterday — the day isn't over, so the
streak is simply still alive). A gap older than that yields 0.

**In the frontend:** `LearningJourney` fetches the daily routine alongside
the journey and renders `DailyRoutine` above the path — the 🔥 streak (or 🌱
with "Let's start today!" when it's a fresh start), today's plan as ⭐/☆
stars plus a small *done/target*, and the 14-day dot calendar. Reusing the
app's existing styles and animations, RTL/LTR aware, no new libraries. The
streak refreshes whenever the child returns to the journey, so playing today
is reflected immediately.

---

## Parent Authentication — accounts, scoping, and the child picker

Only parents have credentials (email + password). Children **never** type a
password — they pick their avatar from the child-picker screen after the parent
is logged in.

**Design decisions:**

- **Passwords are hashed with `passlib[bcrypt]`** — never stored or logged in
  plaintext. `app/core/security.py` provides `hash_password()` / `verify_password()`.
- **Bearer tokens** are HMAC-signed base64 (no JWT library dependency — the
  simplest secure option). Contains `{parent_id, exp}`. Token lifetime is
  configurable via `TIFL_SESSION_EXPIRY_DAYS` (default 30 days). In production
  `TIFL_SECRET_KEY` **must** be set to a strong random value.
- **`parent_id` on `children` table is nullable** — existing children (pre-auth)
  are preserved untouched; they sit with `parent_id=NULL` until claimed. The
  `create_all` call on startup adds the column without touching existing data.
- **No email verification, no password reset, no OAuth** — kept intentionally
  minimal for now. Can be added later.

**Database changes (additive, no migration needed):**

| change | table | why |
|---|---|---|
| new table `parents` | `parents` | parent accounts (id, email, password_hash, name, created_at) |
| new nullable column `parent_id` | `children` | links each child to a parent; existing children stay `NULL` |

`Base.metadata.create_all()` creates the `parents` table and adds the
`parent_id` column as a no-op on an existing `tifl.db` — existing children and
their data are preserved untouched (verified against the real database).

**API routes** (`app/api/auth.py`):

```
POST /api/auth/signup  { email, password, name }  -> { access_token }
POST /api/auth/login   { email, password }         -> { access_token }
GET  /api/auth/me      (Bearer token)              -> { id, email, name, created_at }
```

All `/api/children` endpoints now require a valid bearer token. Children are
scoped: a parent can only see and interact with their own children. Accessing
another parent's child returns 404 (not 403 — to avoid leaking existence).

**Frontend** (`frontend/src/auth/`):

- `AuthProvider` manages token state in React (sessionStorage) and restores on
  mount. All `api.ts` calls include the `Authorization: Bearer` header when a
  token is set.
- `LoginScreen` / `SignupScreen`: clean, adult-facing, bilingual ar/en, RTL/LTR
  aware. Minimum password length is 8 characters.
- `App.tsx` conditionally renders login/signup screens when unauthenticated, or
  the full app (with a logout button in the header) when authenticated.
- `ChildHome` already uses `api.listChildren()` which now returns only the
  logged-in parent's children — no frontend changes needed beyond the auth
  wrapper.

Verify the auth layer end to end (signup, login, me, child creation with
auto parent_id, scoped child list, cross-parent access denied, unauthenticated
denied, password minimum length, duplicate email rejected, invalid token
rejected, missing secret key fails fast, old default rejected — 12 checks):

```bash
python verify_auth.py
```

**Claiming orphaned children (pre-auth data):**

Children that existed before parent authentication was added sit with
`parent_id=NULL` and are unreachable via the API. Run the one-time migration
script to link them to a parent:

```bash
# Creates the parent if needed, links all orphaned children to them.
python link_orphan_children.py --email parent@example.com --name "Parent Name"
```

The script is idempotent — running it again finds nothing to do. It only adds
the `parent_id` column and `parents` table if they don't already exist, and
never modifies or deletes existing child data. All attempts, sessions, goals,
rewards, and mastery records are preserved.

---

## Parent View — today, this week, and gentle home ideas

An adult-facing dashboard that turns the child's existing progress into
plain-language summaries and a few optional home-activity ideas.

**The one governing rule: this view never diagnoses.** It is written for
parents and presents observations and educational tips ONLY. It never:

- diagnoses, or implies a medical/clinical condition,
- gives therapeutic or medical advice,
- states anything as clinical fact.

Every suggestion is a gentle, general, optional idea ("you could try…",
"maybe…"), always phrased as something the *parent* can do — never "your
child has a problem with X". When in doubt, the wording is softened. The
suggestions are **rule-based educational tips** (the exact rules and their
rationale are documented in `app/services/parent_view.py`), not advice.

**Read-only projections, no new source of truth.** Both endpoints derive
everything fresh from the rows the engine / rewards / sessions layers
already own (`Attempt`, `Session`, `LevelUpEvent`, `Skill`, `Rewards`,
`Mastery`). They never write, and they add no new tables or columns —
`Base.metadata.create_all()` on an existing `tifl.db` is a no-op (verified
against the real database: it boots and both endpoints answer 200).

```
GET /api/children/{id}/parent-summary
    -> { child, current_streak, total_stars,
         today: { activities_done, accuracy, sessions_count, stars_earned,
                  skills_practiced: [{skill_id, skill_key, name_ar, name_en}],
                  level_ups },
         week:  { same rollup as today } }

GET /api/children/{id}/suggestions
    -> [ { type, skill: {...}|null, text_ar, text_en, tone: "encouraging" }, ... ]
```

`today` is the current UTC calendar day; `week` is the rolling last
`parent_view_week_days` days (default 7) and therefore includes today.
`stars_earned` is the correct-answer count in the window — the rewards layer
awards exactly one star per exercise solved correctly, so correct attempts
are a faithful projection of stars earned in that window. `accuracy` is
correct / total attempts in the window.

**Suggestion rules** (evaluated in order; always 2–`max_suggestions` items;
every threshold is a config tunable in `app/core/config.py`):

| type | trigger | example wording |
|---|---|---|
| `gentle_practice` | a skill with ≥ `gentle_practice_min_attempts` recent attempts and accuracy ≤ `gentle_practice_max_accuracy` | "You could try a few more [skill] activities together this week — every try counts." |
| `revisit` | a skill with prior practice whose last attempt is more than `revisit_min_days` days ago | "It's been a few days since [skill] — maybe revisit it when you have time." |
| `consistency` | current streak ≥ `consistency_min_streak` | "Great consistency this week — keep the daily routine going." |
| `new_level` | a level-up event within the week window | "Nice progress! [skill] reached a new level." |
| `encouragement` | filler when fewer than two of the above apply | "Keep playing a little every day — small steps add up." |

None of these contains clinical or diagnostic language, and every one is
returned with `tone: "encouraging"`.

**In the frontend:** adult mode now has a small tab switch — **Progress**
(the existing `Dashboard`, unchanged) and **Parent view** (`ParentView`,
new). Parent view has its own child chooser (same pattern as the Dashboard)
and four sections:

1. a today/this-week **snapshot** of simple stat cards (activities,
   accuracy, stars earned, sessions, level-ups, skills practiced);
2. **skill progress** with a friendly, non-clinical status ("doing well" /
   "still practicing" / "getting started");
3. the gentle **home-idea suggestions**, shown as optional ideas with an
   encouraging tone and a "not a diagnosis, not medical advice" note;
4. the last few **session summaries**.

Fully bilingual ar/en with RTL/LTR, reusing the existing styling and API
helpers — no new libraries.

---

## Rewards — stars, streak, and unlockable avatars

A small, purely **positive-reinforcement** layer: nothing ever punishes a wrong
answer. It lives in `app/services/rewards.py`, called from the API layer after
an answer is recorded — `adaptive_engine.record_answer` itself is untouched, so
the pedagogical core is byte-for-byte what it was.

**The three rules:**

1. **Stars.** A star for every exercise solved correctly, no matter how many
   tries it took (a wrong tap simply earns nothing yet — it never costs a
   star, and repetition is never double-rewarded or penalised).
2. **Streak.** Consecutive correct answers build the streak (🔥 ×N). A wrong
   answer resets the counter **quietly** to zero: no punishing message, no
   negative sound, no star deducted.
3. **Avatars.** One new avatar unlocks every
   `rewards_avatar_star_step` stars (default **10**), starting with a free
   starter avatar at 0 stars so a brand-new child always has a colourful
   friend. Unlocked avatars show in colour; locked ones are dimmed into a
   silhouette so the child can see what's coming.

**Storage** — a new table **`Rewards`** (one row per child: `child_id`
unique, `total_stars`, `streak`, `unlocked_avatar_ids` JSON). It is a new
*table*, not new columns on `Child`, on purpose: `Base.metadata.create_all`
(already run on every startup) creates missing tables on an existing database
but would never add columns to an existing one — so this is the only way the
feature appears on a pre-existing `tifl.db` with no manual migration, exactly
like `Goal` and `LevelUpEvent` before it. Verified: dropping the `rewards`
table from a real `tifl.db` and starting the app recreates it with no data
loss.

**Endpoints**

```
GET /api/children/{id}/rewards
    -> { child_id, total_stars, streak, active_avatar,
         avatars: [{ id, emoji, stars, unlocked }, ...] }
```

The avatar catalog (ids, emojis, star thresholds, unlock state) is returned by
the API so the frontend never hardcodes it. Both answer endpoints — `POST
/answers` and `POST /speech-answer` — now include a `rewards` block in their
response (`stars`, `streak`, and `new_avatar` set exactly when that answer
unlocked one). An unclear speech transcript still records nothing and so
neither awards nor resets anything, consistent with the app's no-punishment
design.

**In the frontend:** `ExercisePlayer` shows a ⭐ counter and a 🔥 streak pill
in the top bar (the 🔥 hides at 1 so a fresh child isn't shown a lonely
"×0"), and an avatar that just unlocked triggers a small celebration overlay
reusing the app's existing `animate-cheer`/`animate-pop` — no new libraries.
`ChildHome` shows each child's active avatar, their ⭐ total, and a strip of
all eight avatars: unlocked in full colour, locked as dimmed silhouettes.

---

## Switching to Postgres / Supabase

One line — set an env var, no code changes:

```bash
export TIFL_DATABASE_URL="postgresql+psycopg://user:pass@host:5432/dbname"
```

---

## The single biggest quality upgrade

The exercise `visual` fields currently use emoji and color swatches so the MVP
runs with zero binary assets. Replacing them with **real photos or illustrator
-drawn cards** — and validating the whole exercise set with a **speech therapist
or special-education specialist** — is what turns this from a working prototype
into something usable with real children.
