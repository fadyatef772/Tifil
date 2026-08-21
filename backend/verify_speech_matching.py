"""Verify the Arabic speech ANSWER-MATCHING pipeline -- WITHOUT live audio.

The transcription step needs Whisper weights and a microphone, so it is
covered separately by a manual/live check. Everything after transcription is
deterministic and must be proven here:

  * Arabic normalization (the SAME function is applied to both the transcript
    and the expected option label) folds tashkeel/diacritics and kashida,
    unifies alef forms (أ/إ/آ -> ا), ta marbuta (ة -> ه), alef-maqsura
    (ى -> ي), hamza-on-waw (ؤ -> و), hamza-on-ye (ئ -> ي) and the lam-alef
    ligature (ﻻ -> لا).

  * The fuzzy matcher then turns a messy Whisper/child transcript into a
    confident match on the real option, or an honest "unclear" when nothing
    is close enough (below settings.speech_match_threshold) -- it never
    guesses.

Transcripts below include the ACTUAL outputs observed from Whisper during
diagnosis (e.g. "أحمرو" from whisper-small for أحمر, "أهماعوا" and "أفضل"
from whisper-base), plus noisy orthographic variants a real child + ASR
would produce. No database is touched.

Run:  python verify_speech_matching.py
"""

from app.core.config import settings  # noqa: E402
from app.speech import match  # noqa: E402

THRESHOLD = settings.speech_match_threshold

# --- Fixtures: the same bilingual option shapes the app's exercises use. ---
COLORS = [
    {"id": "red", "label_ar": "أحمر", "label_en": "Red"},
    {"id": "blue", "label_ar": "أزرق", "label_en": "Blue"},
    {"id": "yellow", "label_ar": "أصفر", "label_en": "Yellow"},
]
ANIMALS = [
    {"id": "cat", "label_ar": "قطة", "label_en": "Cat"},
    {"id": "dog", "label_ar": "كلب", "label_en": "Dog"},
    {"id": "duck", "label_ar": "بطة", "label_en": "Duck"},
]
CARS = [
    {"id": "car", "label_ar": "سيارة", "label_en": "Car"},
    {"id": "train", "label_ar": "قطار", "label_en": "Train"},
    {"id": "bike", "label_ar": "دراجة", "label_en": "Bicycle"},
]
GREETINGS = [
    {"id": "salam", "label_ar": "سلام", "label_en": "Hello"},
    {"id": "sabah", "label_ar": "صباح", "label_en": "Morning"},
    {"id": "shukran", "label_ar": "شكرا", "label_en": "Thanks"},
]

COLORS_CORRECT = "red"  # the exercise this child is on


def verdict(res: match.MatchResult, correct_id: str) -> str:
    """Mirror the endpoint's decision logic exactly (routes.py: /speech-answer)."""
    if res.option_id is None or res.score < THRESHOLD:
        return "unclear"
    return "correct" if res.option_id == correct_id else "wrong"


passed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global passed
    if not cond:
        raise AssertionError(f"{name}: FAILED {detail}")
    passed += 1
    print(f"  ok  {name}" + (f"  -- {detail}" if detail else ""))


print("1. Arabic normalization invariants (transcript AND label both pass "
      "through match.normalize)")
check(
    "tashkeel + kashida stripped",
    match.normalize("أَحْـمَر", "ar") == "احمر",
    "أَحْـمَر -> " + repr(match.normalize("أَحْـمَر", "ar")),
)
check(
    "alef-with-hamza folded",
    match.normalize("إحمر", "ar") == "احمر" and match.normalize("آحمر", "ar") == "احمر",
)
check(
    "ta marbuta -> heh",
    match.normalize("قطة", "ar") == "قطه"
    and match.normalize("سيارة", "ar") == "سياره"
    and match.normalize("دراجة", "ar") == "دراجه",
)
check(
    "alef maqsura -> yeh",
    match.normalize("معنى", "ar") == "معني",
)
check(
    "hamza-on-waw -> waw",
    match.normalize("مؤمن", "ar") == "مومن",
    "مؤمن -> " + repr(match.normalize("مؤمن", "ar")),
)
check(
    "hamza-on-ye -> yeh",
    match.normalize("سئارة", "ar") == "سياره",
    "سئارة -> " + repr(match.normalize("سئارة", "ar")),
)
check(
    "lam-alef ligature folded to لا",
    match.normalize("\uFEFB", "ar") == "لا"
    and match.normalize("س\uFEFBم", "ar") == "سلام",
    "FEFB -> " + repr(match.normalize("\uFEFB", "ar")),
)
check(
    "both sides use the same normalization",
    match.normalize("أَحْـمَر", "ar") == match.normalize("احمر", "ar"),
)

print("2. Matcher decisions on real Whisper outputs for a colors exercise "
      "(correct = أحمر/red)")
m = match.best_option_match("أحمرو", COLORS, "ar")  # whisper-small output for أحمر
check(
    "أحمرو (correct word, small) accepted as red",
    m.option_id == "red" and m.score >= THRESHOLD,
    f"matched={m.option_id!r} score={m.score:.2f} -> {verdict(m, COLORS_CORRECT)}",
)
m = match.best_option_match("أهماعوا", COLORS, "ar")  # whisper-base output for أحمر
check(
    "أهماعوا (garbled أحمر, base) honestly unclear",
    m.score < THRESHOLD,
    f"score={m.score:.2f} -> {verdict(m, COLORS_CORRECT)}",
)
m = match.best_option_match("أزرقه", COLORS, "ar")  # whisper-base output for أزرق
check(
    "أزرقه -> confident match to blue (the word actually spoken)",
    m.option_id == "blue" and m.score >= THRESHOLD,
    f"matched={m.option_id!r} score={m.score:.2f} -> {verdict(m, COLORS_CORRECT)}",
)
m = match.best_option_match("أفضل", COLORS, "ar")  # whisper-base output for أصفر
check(
    "أفضل (garbled أصفر, base) honestly unclear",
    m.score < THRESHOLD,
    f"score={m.score:.2f} -> {verdict(m, COLORS_CORRECT)}",
)
m = match.best_option_match("تفاحة", COLORS, "ar")
check(
    "unrelated word stays unclear, never guessed",
    m.score < THRESHOLD,
    f"score={m.score:.2f} -> {verdict(m, COLORS_CORRECT)}",
)

print("3. Noisy real-child/ASR orthography on the correct word")
m = match.best_option_match("أحمر", COLORS, "ar")
check("clean أحمر -> red at 1.0", m.option_id == "red" and m.score == 1.0, f"score={m.score:.2f}")
m = match.best_option_match("إحمر", COLORS, "ar")
check("إحمر (hamza variant) -> red", m.option_id == "red" and m.score == 1.0)
m = match.best_option_match("آحمر", COLORS, "ar")
check("آحمر (hamza variant) -> red", m.option_id == "red" and m.score == 1.0)
m = match.best_option_match("أَحْـمَر", COLORS, "ar")
check("fully vowelled أحمر -> red at 1.0", m.option_id == "red" and m.score == 1.0, f"score={m.score:.2f}")
m = match.best_option_match("احمر", COLORS, "ar")
check("unvowelled احمر -> red", m.option_id == "red" and m.score == 1.0)

print("4. ta-marbuta / hamza / lam-alef inside real words")
m = match.best_option_match("قطه", ANIMALS, "ar")
check("قطه (missing ta-marbuta) -> cat at 1.0", m.option_id == "cat" and m.score == 1.0, f"score={m.score:.2f}")
m = match.best_option_match("بطه", ANIMALS, "ar")
check("بطه -> duck at 1.0", m.option_id == "duck" and m.score == 1.0)
m = match.best_option_match("سئارة", CARS, "ar")
check(
    "سئارة (hamza-on-ye) -> car at 1.0 (exact only thanks to ئ->ي fold)",
    m.option_id == "car" and m.score == 1.0,
    f"score={m.score:.2f}",
)
m = match.best_option_match("دراجه", CARS, "ar")
check("دراجه (ta-marbuta) -> bike at 1.0", m.option_id == "bike" and m.score == 1.0)
m = match.best_option_match("س\uFEFBم", GREETINGS, "ar")
check(
    "سلام written with the lam-alef ligature -> salam at 1.0",
    m.option_id == "salam" and m.score == 1.0,
    f"score={m.score:.2f}",
)

print("5. English path still normalizes and matches")
m = match.best_option_match("Red", COLORS, "en")
check("Red -> red at 1.0", m.option_id == "red" and m.score == 1.0)
m = match.best_option_match("Appel", [{"id": "apple", "label_en": "Apple"}], "en")
check("Appel -> apple (fuzzy)", m.option_id == "apple" and m.score >= THRESHOLD, f"score={m.score:.2f}")
m = match.best_option_match("", COLORS, "ar")
check("empty transcript -> no match at all", m.option_id is None and m.score == 0.0)

print(f"\n{passed} checks passed; speech-match threshold = {THRESHOLD}")
print("ALL CHECKS PASSED")
