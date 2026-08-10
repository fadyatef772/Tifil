"""Seed the database with a starter curriculum.

Categories: cognitive, daily_life, and social (see the "social" skills below).
Bilingual throughout, across four pluggable exercise types (see
app/services/exercise_types/): choice, matching, sequencing, tracing.
Visuals are emoji, hex colors, or words so the MVP runs with zero binary
assets — in production these `visual` fields would point at real photos or
illustrator-drawn cards, which is the single biggest quality upgrade this
app can get.

CONTENT CAVEATS (please read before extending):
  * Emotion content (`emotions` skill) is basic face/word recognition only —
    NOT emotional assessment — and should be reviewed by a specialist.
  * Word/naming content (`picture_naming`) is simple word-recognition only,
    NOT speech therapy; real speech/pronunciation practice must be designed
    with a speech therapist. The optional mic reuses the existing
    speech-answer flow unchanged and is incidental, not a training claim.
  * Social content (`greetings`, `turn_taking`) is vocabulary/sequencing
    practice only — it never evaluates a child's social behavior.

Run:  python -m app.seed   (adds any missing skills/levels idempotently)
      python -m app.seed --reset  (drops the whole db first — WIPES data)
"""

import math

from sqlalchemy import select

from app.core.database import Base, SessionLocal, engine
from app.domain.models import Exercise, Skill, SkillLevel


def _choice(prompt_ar, prompt_en, options, correct_id):
    return {
        "type": "choice",
        "prompt_ar": prompt_ar,
        "prompt_en": prompt_en,
        "options": options,
        "correct_option_id": correct_id,
    }


def _opt(id_, ar, en, visual):
    return {"id": id_, "label_ar": ar, "label_en": en, "visual": visual}


def _pair_item(id_, ar, en, visual):
    return {"id": id_, "label_ar": ar, "label_en": en, "visual": visual}


def _pair(id_, left, right):
    return {"id": id_, "left": left, "right": right}


def _matching(prompt_ar, prompt_en, pairs, answer):
    """Match 2-3 pairs. `answer` maps left item id -> right item id and is
    the server-side pairing truth (stripped from the child payload)."""
    return {
        "type": "matching",
        "prompt_ar": prompt_ar,
        "prompt_en": prompt_en,
        "options": {"pairs": pairs, "answer": answer},
        "correct_option_id": "n/a",
    }


def _seq_item(id_, ar, en, visual, step):
    return {"id": id_, "label_ar": ar, "label_en": en, "visual": visual, "step": step}


def _sequencing(prompt_ar, prompt_en, items, order):
    """Order the given steps. `order` is the correct sequence of item ids
    (stripped from the child payload; each item's `step` is stripped too)."""
    return {
        "type": "sequencing",
        "prompt_ar": prompt_ar,
        "prompt_en": prompt_en,
        "options": {"items": items, "answer": order},
        "correct_option_id": "n/a",
    }


def _tracing(prompt_ar, prompt_en, glyph, visual, guide):
    """Finger-trace a large glyph. `guide` is a polyline in a 0..100
    coordinate space; correctness is a lenient coverage check, NOT
    handwriting recognition (see app/services/exercise_types/tracing.py)."""
    return {
        "type": "tracing",
        "prompt_ar": prompt_ar,
        "prompt_en": prompt_en,
        "options": {"glyph": glyph, "visual": visual, "guide": guide},
        "correct_option_id": "n/a",
    }


# --- Guide polylines (0..100 space) for tracing exercises ------------------
def _poly_guide(pts):
    return [{"x": round(x, 1), "y": round(y, 1)} for x, y in pts]


def _circle_guide(cx=50, cy=50, r=30, n=24):
    return [
        {
            "x": round(cx + r * math.cos(2 * math.pi * i / n), 1),
            "y": round(cy + r * math.sin(2 * math.pi * i / n), 1),
        }
        for i in range(n)
    ]


def _star_guide(cx=50, cy=50, ro=30, ri=15, n=5):
    pts = []
    for i in range(n * 2):
        radius = ro if i % 2 == 0 else ri
        angle = math.pi / 2 + i * math.pi / n
        pts.append((cx + radius * math.cos(angle), cy - radius * math.sin(angle)))
    return _poly_guide(pts)


def _square_guide():
    return _poly_guide([(25, 25), (75, 25), (75, 75), (25, 75), (25, 25)])


# --- Curriculum definition ------------------------------------------------
# Each skill: metadata + a list of levels, each level a list of exercises.
CURRICULUM = [
    {
        "key": "colors",
        "category": "cognitive",
        "name_ar": "الألوان",
        "name_en": "Colors",
        "icon": "palette",
        "levels": [
            {
                "name_ar": "ألوان أساسية",
                "name_en": "Basic colors",
                "exercises": [
                    _choice(
                        "لمس اللون الأحمر", "Touch the red one",
                        [
                            _opt("red", "أحمر", "Red", "#E24B4A"),
                            _opt("blue", "أزرق", "Blue", "#378ADD"),
                            _opt("yellow", "أصفر", "Yellow", "#EF9F27"),
                        ],
                        "red",
                    ),
                    _choice(
                        "لمس اللون الأزرق", "Touch the blue one",
                        [
                            _opt("red", "أحمر", "Red", "#E24B4A"),
                            _opt("blue", "أزرق", "Blue", "#378ADD"),
                            _opt("yellow", "أصفر", "Yellow", "#EF9F27"),
                        ],
                        "blue",
                    ),
                    _choice(
                        "لمس اللون الأصفر", "Touch the yellow one",
                        [
                            _opt("yellow", "أصفر", "Yellow", "#EF9F27"),
                            _opt("blue", "أزرق", "Blue", "#378ADD"),
                        ],
                        "yellow",
                    ),
                ],
            },
            {
                "name_ar": "ألوان أكثر",
                "name_en": "More colors",
                "exercises": [
                    _choice(
                        "لمس اللون الأخضر", "Touch the green one",
                        [
                            _opt("green", "أخضر", "Green", "#639922"),
                            _opt("purple", "بنفسجي", "Purple", "#7F77DD"),
                            _opt("orange", "برتقالي", "Orange", "#D85A30"),
                            _opt("red", "أحمر", "Red", "#E24B4A"),
                        ],
                        "green",
                    ),
                    _choice(
                        "لمس اللون البنفسجي", "Touch the purple one",
                        [
                            _opt("green", "أخضر", "Green", "#639922"),
                            _opt("purple", "بنفسجي", "Purple", "#7F77DD"),
                            _opt("orange", "برتقالي", "Orange", "#D85A30"),
                        ],
                        "purple",
                    ),
                    _choice(
                        "لمس اللون البرتقالي", "Touch the orange one",
                        [
                            _opt("orange", "برتقالي", "Orange", "#D85A30"),
                            _opt("green", "أخضر", "Green", "#639922"),
                            _opt("blue", "أزرق", "Blue", "#378ADD"),
                        ],
                        "orange",
                    ),
                ],
            },
            {
                "name_ar": "لون واسمه",
                "name_en": "Match color to name",
                "exercises": [
                    _matching(
                        "وصّل كل لون باسمه", "Match each color to its name",
                        [
                            _pair(
                                "c1",
                                _pair_item("L_red", "أحمر", "Red", "#E24B4A"),
                                _pair_item("R_red", "أحمر", "Red", "أحمر"),
                            ),
                            _pair(
                                "c2",
                                _pair_item("L_blue", "أزرق", "Blue", "#378ADD"),
                                _pair_item("R_blue", "أزرق", "Blue", "أزرق"),
                            ),
                            _pair(
                                "c3",
                                _pair_item("L_green", "أخضر", "Green", "#639922"),
                                _pair_item("R_green", "أخضر", "Green", "أخضر"),
                            ),
                        ],
                        {"L_red": "R_red", "L_blue": "R_blue", "L_green": "R_green"},
                    ),
                    _matching(
                        "وصّل كل لون باسمه", "Match each color to its name",
                        [
                            _pair(
                                "c4",
                                _pair_item("L_yellow", "أصفر", "Yellow", "#EF9F27"),
                                _pair_item("R_yellow", "أصفر", "Yellow", "أصفر"),
                            ),
                            _pair(
                                "c5",
                                _pair_item("L_orange", "برتقالي", "Orange", "#D85A30"),
                                _pair_item("R_orange", "برتقالي", "Orange", "برتقالي"),
                            ),
                            _pair(
                                "c6",
                                _pair_item("L_purple", "بنفسجي", "Purple", "#7F77DD"),
                                _pair_item("R_purple", "بنفسجي", "Purple", "بنفسجي"),
                            ),
                        ],
                        {
                            "L_yellow": "R_yellow",
                            "L_orange": "R_orange",
                            "L_purple": "R_purple",
                        },
                    ),
                ],
            },
        ],
    },
    {
        "key": "numbers",
        "category": "cognitive",
        "name_ar": "الأرقام",
        "name_en": "Numbers",
        "icon": "numbers",
        "levels": [
            {
                "name_ar": "من ١ إلى ٣",
                "name_en": "One to three",
                "exercises": [
                    _choice(
                        "لمس رقم واحد", "Touch number one",
                        [
                            _opt("1", "١", "1", "1️⃣"),
                            _opt("2", "٢", "2", "2️⃣"),
                            _opt("3", "٣", "3", "3️⃣"),
                        ],
                        "1",
                    ),
                    _choice(
                        "لمس رقم اتنين", "Touch number two",
                        [
                            _opt("1", "١", "1", "1️⃣"),
                            _opt("2", "٢", "2", "2️⃣"),
                            _opt("3", "٣", "3", "3️⃣"),
                        ],
                        "2",
                    ),
                    _choice(
                        "لمس الصورة اللي فيها تفاحتين", "Touch two apples",
                        [
                            _opt("one", "تفاحة", "One apple", "🍎"),
                            _opt("two", "تفاحتين", "Two apples", "🍎🍎"),
                        ],
                        "two",
                    ),
                ],
            },
            {
                "name_ar": "من ١ إلى ٥",
                "name_en": "One to five",
                "exercises": [
                    _choice(
                        "لمس رقم أربعة", "Touch number four",
                        [
                            _opt("3", "٣", "3", "3️⃣"),
                            _opt("4", "٤", "4", "4️⃣"),
                            _opt("5", "٥", "5", "5️⃣"),
                        ],
                        "4",
                    ),
                    _choice(
                        "لمس رقم خمسة", "Touch number five",
                        [
                            _opt("4", "٤", "4", "4️⃣"),
                            _opt("5", "٥", "5", "5️⃣"),
                            _opt("2", "٢", "2", "2️⃣"),
                        ],
                        "5",
                    ),
                ],
            },
            {
                "name_ar": "رقم وعدد",
                "name_en": "Number and quantity",
                "exercises": [
                    _matching(
                        "وصّل كل رقم بالعدد الصح", "Match each number to the right count",
                        [
                            _pair(
                                "n1",
                                _pair_item("L_1", "١", "1", "1️⃣"),
                                _pair_item("R_1", "تفاحة", "1 apple", "🍎"),
                            ),
                            _pair(
                                "n2",
                                _pair_item("L_2", "٢", "2", "2️⃣"),
                                _pair_item("R_2", "تفاحتين", "2 apples", "🍎🍎"),
                            ),
                            _pair(
                                "n3",
                                _pair_item("L_3", "٣", "3", "3️⃣"),
                                _pair_item("R_3", "٣ تفاح", "3 apples", "🍎🍎🍎"),
                            ),
                        ],
                        {"L_1": "R_1", "L_2": "R_2", "L_3": "R_3"},
                    ),
                    _matching(
                        "وصّل كل رقم بالعدد الصح", "Match each number to the right count",
                        [
                            _pair(
                                "n4",
                                _pair_item("L_4", "٤", "4", "4️⃣"),
                                _pair_item("R_4", "٤ تفاح", "4 apples", "🍎🍎🍎🍎"),
                            ),
                            _pair(
                                "n5",
                                _pair_item("L_5", "٥", "5", "5️⃣"),
                                _pair_item("R_5", "٥ تفاح", "5 apples", "🍎🍎🍎🍎🍎"),
                            ),
                        ],
                        {"L_4": "R_4", "L_5": "R_5"},
                    ),
                ],
            },
        ],
    },
    {
        "key": "handwashing",
        "category": "daily_life",
        "name_ar": "غسيل الإيدين",
        "name_en": "Washing hands",
        "icon": "hand-stop",
        "levels": [
            {
                "name_ar": "الخطوة الأولى",
                "name_en": "First step",
                "exercises": [
                    _choice(
                        "إيه أول حاجة نعملها؟", "What do we do first?",
                        [
                            _opt("water", "نفتح الميّة", "Turn on water", "🚰"),
                            _opt("dry", "ننشّف", "Dry hands", "🧻"),
                        ],
                        "water",
                    ),
                    _choice(
                        "بعد الميّة نستخدم إيه؟", "After water, what do we use?",
                        [
                            _opt("soap", "الصابون", "Soap", "🧼"),
                            _opt("towel", "الفوطة", "Towel", "🧺"),
                        ],
                        "soap",
                    ),
                ],
            },
            {
                "name_ar": "نكمّل لوحدنا",
                "name_en": "Finish on our own",
                "exercises": [
                    _choice(
                        "بعد الصابون نعمل إيه؟", "After soap, what next?",
                        [
                            _opt("rinse", "نشطف بالميّة", "Rinse with water", "💧"),
                            _opt("eat", "ناكل", "Eat", "🍽️"),
                        ],
                        "rinse",
                    ),
                    _choice(
                        "آخر خطوة إيه؟", "What is the last step?",
                        [
                            _opt("dry", "ننشّف إيدينا", "Dry our hands", "🧻"),
                            _opt("water", "نفتح الميّة", "Turn on water", "🚰"),
                        ],
                        "dry",
                    ),
                ],
            },
            {
                "name_ar": "نرتب الخطوات",
                "name_en": "Order the steps",
                "exercises": [
                    _sequencing(
                        "رتب خطوات غسيل الإيدين", "Put the handwashing steps in order",
                        [
                            _seq_item("s_soap", "الصابون", "Soap", "🧼", 1),
                            _seq_item("s_rub", "نفرك إيدينا", "Rub our hands", "🤲", 2),
                            _seq_item("s_rinse", "نشطف", "Rinse", "💧", 3),
                        ],
                        ["s_soap", "s_rub", "s_rinse"],
                    ),
                    _sequencing(
                        "رتب خطوات غسيل الإيدين", "Put the handwashing steps in order",
                        [
                            _seq_item("s_water", "نفتح الميّة", "Turn on water", "🚰", 1),
                            _seq_item("s_soap2", "الصابون", "Soap", "🧼", 2),
                            _seq_item("s_dry", "ننشّف إيدينا", "Dry our hands", "🧻", 3),
                        ],
                        ["s_water", "s_soap2", "s_dry"],
                    ),
                ],
            },
        ],
    },
    {
        "key": "dressing",
        "category": "daily_life",
        "name_ar": "نلبس هدومنا",
        "name_en": "Getting dressed",
        "icon": "shirt",
        "levels": [
            {
                "name_ar": "نعرف الهدوم",
                "name_en": "Know our clothes",
                "exercises": [
                    _choice(
                        "لمس القميص", "Touch the shirt",
                        [
                            _opt("shirt", "قميص", "Shirt", "👕"),
                            _opt("shoe", "جزمة", "Shoe", "👟"),
                            _opt("hat", "قبعة", "Hat", "🧢"),
                        ],
                        "shirt",
                    ),
                    _choice(
                        "لمس الجزمة", "Touch the shoe",
                        [
                            _opt("shirt", "قميص", "Shirt", "👕"),
                            _opt("shoe", "جزمة", "Shoe", "👟"),
                            _opt("socks", "شراب", "Socks", "🧦"),
                        ],
                        "shoe",
                    ),
                ],
            },
            {
                "name_ar": "الترتيب الصح",
                "name_en": "The right order",
                "exercises": [
                    _choice(
                        "بنلبس الشراب قبل ولا بعد الجزمة؟",
                        "Socks before or after shoes?",
                        [
                            _opt("before", "قبل", "Before", "🧦"),
                            _opt("after", "بعد", "After", "👟"),
                        ],
                        "before",
                    ),
                ],
            },
            {
                "name_ar": "نرتب هدومنا",
                "name_en": "Order our clothes",
                "exercises": [
                    _sequencing(
                        "رتب هدومك بالترتيب الصح", "Put your clothes on in the right order",
                        [
                            _seq_item("s_shirt", "قميص", "Shirt", "👕", 1),
                            _seq_item("s_pants", "بنطلون", "Pants", "👖", 2),
                            _seq_item("s_shoes", "جزمة", "Shoes", "👟", 3),
                        ],
                        ["s_shirt", "s_pants", "s_shoes"],
                    ),
                ],
            },
        ],
    },
    {
        "key": "shapes",
        "category": "cognitive",
        "name_ar": "الأشكال",
        "name_en": "Shapes",
        "icon": "shapes",
        "levels": [
            {
                "name_ar": "أشكال أساسية",
                "name_en": "Basic shapes",
                "exercises": [
                    _choice(
                        "لمس الدايرة", "Touch the circle",
                        [
                            _opt("circle", "دايرة", "Circle", "⭕"),
                            _opt("square", "مربع", "Square", "⬜"),
                            _opt("star", "نجمة", "Star", "⭐"),
                        ],
                        "circle",
                    ),
                    _choice(
                        "لمس المربع", "Touch the square",
                        [
                            _opt("square", "مربع", "Square", "⬜"),
                            _opt("triangle", "مثلث", "Triangle", "🔺"),
                            _opt("circle", "دايرة", "Circle", "⭕"),
                        ],
                        "square",
                    ),
                    _choice(
                        "لمس النجمة", "Touch the star",
                        [
                            _opt("star", "نجمة", "Star", "⭐"),
                            _opt("circle", "دايرة", "Circle", "⭕"),
                            _opt("square", "مربع", "Square", "⬜"),
                        ],
                        "star",
                    ),
                ],
            },
            {
                "name_ar": "نتتبّع الأشكال",
                "name_en": "Trace the shapes",
                "exercises": [
                    _tracing(
                        "امسح على الدايرة", "Trace the circle",
                        "circle", "⭕", _circle_guide(),
                    ),
                    _tracing(
                        "امسح على المربع", "Trace the square",
                        "square", "⬜", _square_guide(),
                    ),
                    _tracing(
                        "امسح على النجمة", "Trace the star",
                        "star", "⭐", _star_guide(),
                    ),
                ],
            },
            {
                "name_ar": "أسماء الأشكال",
                "name_en": "Shape names",
                "exercises": [
                    _choice(
                        "لمس المثلث", "Touch the triangle",
                        [
                            _opt("triangle", "مثلث", "Triangle", "🔺"),
                            _opt("circle", "دايرة", "Circle", "⭕"),
                            _opt("square", "مربع", "Square", "⬜"),
                            _opt("star", "نجمة", "Star", "⭐"),
                        ],
                        "triangle",
                    ),
                    _choice(
                        "لمس النجمة", "Touch the star",
                        [
                            _opt("star", "نجمة", "Star", "⭐"),
                            _opt("triangle", "مثلث", "Triangle", "🔺"),
                            _opt("circle", "دايرة", "Circle", "⭕"),
                        ],
                        "star",
                    ),
                ],
            },
        ],
    },
    {
        "key": "animals",
        "category": "cognitive",
        "name_ar": "الحيوانات",
        "name_en": "Animals",
        "icon": "paw",
        "levels": [
            {
                "name_ar": "نتعرّف على الحيوانات",
                "name_en": "Meet the animals",
                "exercises": [
                    _choice(
                        "لمس القطة", "Touch the cat",
                        [
                            _opt("cat", "قطة", "Cat", "🐱"),
                            _opt("dog", "كلب", "Dog", "🐶"),
                            _opt("bird", "عصفور", "Bird", "🐦"),
                        ],
                        "cat",
                    ),
                    _choice(
                        "لمس الكلب", "Touch the dog",
                        [
                            _opt("dog", "كلب", "Dog", "🐶"),
                            _opt("cat", "قطة", "Cat", "🐱"),
                            _opt("rabbit", "أرنب", "Rabbit", "🐰"),
                        ],
                        "dog",
                    ),
                    _choice(
                        "لمس العصفور", "Touch the bird",
                        [
                            _opt("bird", "عصفور", "Bird", "🐦"),
                            _opt("dog", "كلب", "Dog", "🐶"),
                            _opt("cat", "قطة", "Cat", "🐱"),
                        ],
                        "bird",
                    ),
                ],
            },
            {
                "name_ar": "صوت الحيوانات",
                "name_en": "Animal sounds",
                "exercises": [
                    _matching(
                        "وصّل كل حيوان بصوته", "Match each animal to its sound",
                        [
                            _pair(
                                "a1",
                                _pair_item("L_dog", "كلب", "Dog", "🐶"),
                                _pair_item("R_dog", "هوه هوه", "Woof", "🐕"),
                            ),
                            _pair(
                                "a2",
                                _pair_item("L_cat", "قطة", "Cat", "🐱"),
                                _pair_item("R_cat", "مياو", "Meow", "🐈"),
                            ),
                            _pair(
                                "a3",
                                _pair_item("L_bird", "عصفور", "Bird", "🐦"),
                                _pair_item("R_bird", "غرد غرد", "Chirp", "🐤"),
                            ),
                        ],
                        {"L_dog": "R_dog", "L_cat": "R_cat", "L_bird": "R_bird"},
                    ),
                    _choice(
                        "مين بيقول مياو؟", "Who says meow?",
                        [
                            _opt("cat", "القطة", "The cat", "🐱"),
                            _opt("dog", "الكلب", "The dog", "🐶"),
                            _opt("bird", "العصفور", "The bird", "🐦"),
                        ],
                        "cat",
                    ),
                ],
            },
            {
                "name_ar": "مين اللي بيقول إيه",
                "name_en": "Who says what",
                "exercises": [
                    _choice(
                        "مين بيقول هوه هوه؟", "Who says woof?",
                        [
                            _opt("dog", "الكلب", "The dog", "🐶"),
                            _opt("cat", "القطة", "The cat", "🐱"),
                        ],
                        "dog",
                    ),
                    _choice(
                        "مين بيغرد؟", "Who chirps?",
                        [
                            _opt("bird", "العصفور", "The bird", "🐦"),
                            _opt("cat", "القطة", "The cat", "🐱"),
                        ],
                        "bird",
                    ),
                ],
            },
        ],
    },
    {
        # --- Feelings recognition (basic) ------------------------------------
        # REVIEW CAVEAT: this is basic recognition of happy/sad/angry/scared
        # faces (choice) and matching a face to its word — it is NOT an
        # emotional assessment and must not be read as one. Emotion content
        # like this should be reviewed by a specialist (psychologist or
        # special-education therapist) before use with real children.
        "key": "emotions",
        "category": "cognitive",
        "name_ar": "المشاعر",
        "name_en": "Feelings",
        "icon": "smile",
        "levels": [
            {
                "name_ar": "نعرف المشاعر",
                "name_en": "Know the feelings",
                "exercises": [
                    _choice(
                        "لمس الوش السعيد", "Touch the happy face",
                        [
                            _opt("happy", "سعيد", "Happy", "😀"),
                            _opt("sad", "حزين", "Sad", "😢"),
                            _opt("angry", "غضبان", "Angry", "😠"),
                        ],
                        "happy",
                    ),
                    _choice(
                        "لمس الوش الحزين", "Touch the sad face",
                        [
                            _opt("sad", "حزين", "Sad", "😢"),
                            _opt("happy", "سعيد", "Happy", "😀"),
                            _opt("scared", "خايف", "Scared", "😨"),
                        ],
                        "sad",
                    ),
                    _choice(
                        "لمس الوش الغضبان", "Touch the angry face",
                        [
                            _opt("angry", "غضبان", "Angry", "😠"),
                            _opt("sad", "حزين", "Sad", "😢"),
                            _opt("happy", "سعيد", "Happy", "😀"),
                        ],
                        "angry",
                    ),
                ],
            },
            {
                "name_ar": "مين حاسس إيه",
                "name_en": "Who feels what",
                "exercises": [
                    _matching(
                        "وصّل كل وش بمشاعره", "Match each face to its feeling",
                        [
                            _pair(
                                "e1",
                                _pair_item("L_happy", "سعيد", "Happy", "😀"),
                                _pair_item("R_happy", "سعيد", "Happy", "🥳"),
                            ),
                            _pair(
                                "e2",
                                _pair_item("L_sad", "حزين", "Sad", "😢"),
                                _pair_item("R_sad", "حزين", "Sad", "😞"),
                            ),
                            _pair(
                                "e3",
                                _pair_item("L_angry", "غضبان", "Angry", "😠"),
                                _pair_item("R_angry", "غضبان", "Angry", "😡"),
                            ),
                        ],
                        {
                            "L_happy": "R_happy",
                            "L_sad": "R_sad",
                            "L_angry": "R_angry",
                        },
                    ),
                    _matching(
                        "وصّل كل وش بمشاعره", "Match each face to its feeling",
                        [
                            _pair(
                                "e4",
                                _pair_item("L_scared", "خايف", "Scared", "😨"),
                                _pair_item("R_scared", "خايف", "Scared", "😱"),
                            ),
                            _pair(
                                "e5",
                                _pair_item("L_happy2", "سعيد", "Happy", "😊"),
                                _pair_item("R_happy2", "سعيد", "Happy", "😄"),
                            ),
                        ],
                        {"L_scared": "R_scared", "L_happy2": "R_happy2"},
                    ),
                ],
            },
            {
                "name_ar": "نلمس المشاعر",
                "name_en": "Touch the feelings",
                "exercises": [
                    _choice(
                        "لمس الوش الخايف", "Touch the scared face",
                        [
                            _opt("scared", "خايف", "Scared", "😨"),
                            _opt("happy", "سعيد", "Happy", "😀"),
                            _opt("angry", "غضبان", "Angry", "😠"),
                        ],
                        "scared",
                    ),
                    _choice(
                        "لمس الوش السعيد", "Touch the happy face",
                        [
                            _opt("happy", "سعيد", "Happy", "😊"),
                            _opt("sad", "حزين", "Sad", "😢"),
                        ],
                        "happy",
                    ),
                ],
            },
        ],
    },
    {
        "key": "body_parts",
        "category": "daily_life",
        "name_ar": "جسمنا",
        "name_en": "Our body",
        "icon": "hand",
        "levels": [
            {
                "name_ar": "أجزاء الجسم",
                "name_en": "Body parts",
                "exercises": [
                    _choice(
                        "لمس الأنف", "Touch the nose",
                        [
                            _opt("nose", "أنف", "Nose", "👃"),
                            _opt("ear", "ودن", "Ear", "👂"),
                            _opt("hand", "إيد", "Hand", "🖐️"),
                        ],
                        "nose",
                    ),
                    _choice(
                        "لمس العينين", "Touch the eyes",
                        [
                            _opt("eyes", "عينين", "Eyes", "👀"),
                            _opt("nose", "أنف", "Nose", "👃"),
                            _opt("ear", "ودن", "Ear", "👂"),
                        ],
                        "eyes",
                    ),
                    _choice(
                        "لمس الإيدين", "Touch the hands",
                        [
                            _opt("hand", "إيدين", "Hands", "🖐️"),
                            _opt("eyes", "عينين", "Eyes", "👀"),
                            _opt("mouth", "فم", "Mouth", "👄"),
                        ],
                        "hand",
                    ),
                ],
            },
            {
                "name_ar": "كمان جزء",
                "name_en": "More parts",
                "exercises": [
                    _choice(
                        "لمس الفم", "Touch the mouth",
                        [
                            _opt("mouth", "فم", "Mouth", "👄"),
                            _opt("ear", "ودن", "Ear", "👂"),
                            _opt("nose", "أنف", "Nose", "👃"),
                        ],
                        "mouth",
                    ),
                    _choice(
                        "لمس الودان", "Touch the ears",
                        [
                            _opt("ear", "ودان", "Ears", "👂"),
                            _opt("mouth", "فم", "Mouth", "👄"),
                            _opt("eyes", "عينين", "Eyes", "👀"),
                        ],
                        "ear",
                    ),
                    _choice(
                        "لمس الرجلين", "Touch the feet",
                        [
                            _opt("feet", "رجلين", "Feet", "🦶"),
                            _opt("mouth", "فم", "Mouth", "👄"),
                            _opt("ear", "ودن", "Ear", "👂"),
                        ],
                        "feet",
                    ),
                ],
            },
        ],
    },
    {
        "key": "morning_routine",
        "category": "daily_life",
        "name_ar": "الروتين الصباحي",
        "name_en": "Morning routine",
        "icon": "sun",
        "levels": [
            {
                "name_ar": "نبدأ النهارده",
                "name_en": "Start our day",
                "exercises": [
                    _choice(
                        "أول حاجة في الصبح نعمل إيه؟",
                        "What do we do first in the morning?",
                        [
                            _opt("wake", "نصحي", "Wake up", "🛏️"),
                            _opt("breakfast", "نتغدى", "Eat breakfast", "🥣"),
                        ],
                        "wake",
                    ),
                    _choice(
                        "بعد ما نصحي نغسل إيه؟", "After waking up, what do we wash?",
                        [
                            _opt("face", "وشنا", "Our face", "💧"),
                            _opt("feet", "رجلينا", "Our feet", "🦶"),
                        ],
                        "face",
                    ),
                ],
            },
            {
                "name_ar": "نرتب الروتين",
                "name_en": "Order the routine",
                "exercises": [
                    _sequencing(
                        "رتب الروتين الصباحي", "Put the morning routine in order",
                        [
                            _seq_item("s_wake", "نصحي", "Wake up", "🛏️", 1),
                            _seq_item("s_wash", "نغسل وشنا", "Wash our face", "💧", 2),
                            _seq_item("s_breakfast", "نتغدى", "Eat breakfast", "🥣", 3),
                        ],
                        ["s_wake", "s_wash", "s_breakfast"],
                    ),
                ],
            },
            {
                "name_ar": "نكمل اليوم",
                "name_en": "Finish our morning",
                "exercises": [
                    _choice(
                        "بعد الفطار نعمل إيه؟", "After breakfast, what do we do?",
                        [
                            _opt("brush", "ننضف سناننا", "Brush our teeth", "🪥"),
                            _opt("sleep", "ننام", "Sleep", "😴"),
                        ],
                        "brush",
                    ),
                    _choice(
                        "بعد ما نصحى نلبس إيه؟", "After waking up, what do we put on?",
                        [
                            _opt("clothes", "هدومنا", "Our clothes", "👕"),
                            _opt("shoes_only", "جزمة بس", "Only shoes", "👟"),
                        ],
                        "clothes",
                    ),
                ],
            },
        ],
    },
    {
        # --- Social skill: greetings (choice) --------------------------------
        # Situation -> greeting. Strictly behavioral, culturally neutral enough
        # for the MVP (morning/hello/goodbye/polite words). No assumptions are
        # made about a child's social ability — this is just vocabulary practice.
        "key": "greetings",
        "category": "social",
        "name_ar": "التحية",
        "name_en": "Greetings",
        "icon": "wave",
        "levels": [
            {
                "name_ar": "بنقول إيه؟",
                "name_en": "What do we say?",
                "exercises": [
                    _choice(
                        "في الصبح بنقول إيه؟", "In the morning, what do we say?",
                        [
                            _opt("g_am", "صباح الخير", "Good morning", "🌅"),
                            _opt("g_ng", "تصبح على خير", "Good night", "🌙"),
                            _opt("g_bye", "مع السلامة", "Goodbye", "👋"),
                        ],
                        "g_am",
                    ),
                    _choice(
                        "لما نلاقي صاحبنا بنقول إيه؟",
                        "When we meet a friend, what do we say?",
                        [
                            _opt("g_hi", "أهلاً", "Hello", "🙂"),
                            _opt("g_bye", "مع السلامة", "Goodbye", "👋"),
                            _opt("g_ng", "تصبح على خير", "Good night", "🌙"),
                        ],
                        "g_hi",
                    ),
                    _choice(
                        "لما صاحبنا يروح بنقول إيه؟",
                        "When our friend leaves, what do we say?",
                        [
                            _opt("g_bye", "مع السلامة", "Goodbye", "👋"),
                            _opt("g_am", "صباح الخير", "Good morning", "🌅"),
                            _opt("g_thx", "شكراً", "Thank you", "🙏"),
                        ],
                        "g_bye",
                    ),
                ],
            },
            {
                "name_ar": "كلمات مهذبة",
                "name_en": "Polite words",
                "exercises": [
                    _choice(
                        "لما حد يساعدنا بنقول إيه؟",
                        "When someone helps us, what do we say?",
                        [
                            _opt("g_thx", "شكراً", "Thank you", "🙏"),
                            _opt("g_pls", "من فضلك", "Please", "🤲"),
                            _opt("g_hi", "أهلاً", "Hello", "🙂"),
                        ],
                        "g_thx",
                    ),
                    _choice(
                        "لما نطلب حاجة بنقول إيه؟",
                        "When we ask for something, what do we say?",
                        [
                            _opt("g_pls", "من فضلك", "Please", "🤲"),
                            _opt("g_bye", "مع السلامة", "Goodbye", "👋"),
                            _opt("g_ng", "تصبح على خير", "Good night", "🌙"),
                        ],
                        "g_pls",
                    ),
                ],
            },
        ],
    },
    {
        # --- Social skill: taking turns / sharing (sequencing) ---------------
        # Simple 3-step social routines. Sequencing only — no judgment of the
        # child's social behavior; the child is just ordering what to do.
        "key": "turn_taking",
        "category": "social",
        "name_ar": "نتبادل الدور",
        "name_en": "Taking turns",
        "icon": "handshake",
        "levels": [
            {
                "name_ar": "نلعب سوا",
                "name_en": "Play together",
                "exercises": [
                    _sequencing(
                        "رتب: إزاي نطلب ونتناوب",
                        "Order: how we ask and take turns",
                        [
                            _seq_item("s_ask", "بنسأل: ممكن ألعب بعدك؟",
                                      "We ask: may I play after you?", "🙋", 1),
                            _seq_item("s_wait", "نستنى دورنا",
                                      "We wait our turn", "⏳", 2),
                            _seq_item("s_thx", "نقول شكراً",
                                      "We say thank you", "🙏", 3),
                        ],
                        ["s_ask", "s_wait", "s_thx"],
                    ),
                    _sequencing(
                        "رتب: إزاي نشارك",
                        "Order: how we share",
                        [
                            _seq_item("s_share", "بنشارك اللعبة",
                                      "We share the toy", "🧸", 1),
                            _seq_item("s_play", "نلعب سوا",
                                      "We play together", "🎲", 2),
                            _seq_item("s_happy", "نفرح سوا",
                                      "We enjoy together", "😊", 3),
                        ],
                        ["s_share", "s_play", "s_happy"],
                    ),
                ],
            },
            {
                "name_ar": "نستنى دورنا",
                "name_en": "Waiting our turn",
                "exercises": [
                    _sequencing(
                        "رتب: دورنا على الزلّاقة",
                        "Order: our turn on the slide",
                        [
                            _seq_item("s_line", "نقف في الطابور",
                                      "We stand in line", "🚶", 1),
                            _seq_item("s_slide", "ننزل من الزلّاقة",
                                      "We go down the slide", "🛝", 2),
                            _seq_item("s_next", "نفضل دور اللي بعده",
                                      "The next friend goes", "🙌", 3),
                        ],
                        ["s_line", "s_slide", "s_next"],
                    ),
                    _sequencing(
                        "رتب: إزاي نتكلم مع صاحبنا",
                        "Order: how we talk with a friend",
                        [
                            _seq_item("s_hi", "بنقول أهلاً",
                                      "We say hello", "👋", 1),
                            _seq_item("s_listen", "بنسمع صاحبنا",
                                      "We listen to our friend", "👂", 2),
                            _seq_item("s_reply", "نرد عليه",
                                      "We reply", "💬", 3),
                        ],
                        ["s_hi", "s_listen", "s_reply"],
                    ),
                ],
            },
        ],
    },
    {
        # --- Memory skill: matching pairs (matching) -------------------------
        # Pure visual memory: match identical items (L1) then things used
        # together (L2). No timing, no pressure — tap and match at your pace.
        "key": "memory_pairs",
        "category": "cognitive",
        "name_ar": "ذاكرة الصور",
        "name_en": "Picture memory",
        "icon": "memory",
        "levels": [
            {
                "name_ar": "نفس الشكل",
                "name_en": "Identical pairs",
                "exercises": [
                    _matching(
                        "وصّل كل حيوان بنفسه",
                        "Match each animal to its twin",
                        [
                            _pair("mp1", _pair_item("L_cat", "قطة", "Cat", "🐱"),
                                  _pair_item("R_cat", "قطة", "Cat", "🐱")),
                            _pair("mp2", _pair_item("L_dog", "كلب", "Dog", "🐶"),
                                  _pair_item("R_dog", "كلب", "Dog", "🐶")),
                            _pair("mp3", _pair_item("L_bird", "عصفور", "Bird", "🐦"),
                                  _pair_item("R_bird", "عصفور", "Bird", "🐦")),
                        ],
                        {"L_cat": "R_cat", "L_dog": "R_dog", "L_bird": "R_bird"},
                    ),
                    _matching(
                        "وصّل كل حاجة بنفسها",
                        "Match each thing to its twin",
                        [
                            _pair("mp4", _pair_item("L_apple", "تفاحة", "Apple", "🍎"),
                                  _pair_item("R_apple", "تفاحة", "Apple", "🍎")),
                            _pair("mp5", _pair_item("L_ball", "كرة", "Ball", "⚽"),
                                  _pair_item("R_ball", "كرة", "Ball", "⚽")),
                            _pair("mp6", _pair_item("L_sun", "شمس", "Sun", "☀️"),
                                  _pair_item("R_sun", "شمس", "Sun", "☀️")),
                        ],
                        {"L_apple": "R_apple", "L_ball": "R_ball", "L_sun": "R_sun"},
                    ),
                ],
            },
            {
                "name_ar": "حاجات بنستخدمها مع بعض",
                "name_en": "Things we use together",
                "exercises": [
                    _matching(
                        "وصّل كل حاجة باللي تناسبها",
                        "Match each thing to what goes with it",
                        [
                            _pair("mp7", _pair_item("L_sock", "شراب", "Socks", "🧦"),
                                  _pair_item("R_shoe", "جزمة", "Shoes", "👟")),
                            _pair("mp8", _pair_item("L_glove", "جوانتي", "Gloves", "🧤"),
                                  _pair_item("R_scarf", "شال", "Scarf", "🧣")),
                            _pair("mp9", _pair_item("L_hat", "قبعة", "Hat", "🧢"),
                                  _pair_item("R_glasses", "نظارة", "Glasses", "🕶️")),
                        ],
                        {"L_sock": "R_shoe", "L_glove": "R_scarf", "L_hat": "R_glasses"},
                    ),
                    _matching(
                        "وصّل كل حاجة باللي تناسبها",
                        "Match each thing to what goes with it",
                        [
                            _pair("mp10", _pair_item("L_spoon", "معلقة", "Spoon", "🥄"),
                                   _pair_item("R_soup", "شوربة", "Soup", "🍲")),
                            _pair("mp11", _pair_item("L_cup", "فنجان", "Cup", "☕"),
                                   _pair_item("R_tea", "شاي", "Tea", "🍵")),
                            _pair("mp12", _pair_item("L_plate", "طبق", "Plate", "🍽️"),
                                   _pair_item("R_food", "أكل", "Food", "🍔")),
                        ],
                        {"L_spoon": "R_soup", "L_cup": "R_tea", "L_plate": "R_food"},
                    ),
                ],
            },
        ],
    },
    {
        # --- Memory skill: what's missing / recall (choice) ------------------
        # A tiny, STATIC recall: the prompt names a small set (read aloud),
        # and the child picks which item belongs to that set. No timing, no
        # hidden-then-reveal mechanics — keep it gentle and predictable.
        "key": "recall",
        "category": "cognitive",
        "name_ar": "نتفكر مع بعض",
        "name_en": "Let's remember",
        "icon": "magnifier",
        "levels": [
            {
                "name_ar": "نتفكر اللي شفناه",
                "name_en": "Remember what we saw",
                "exercises": [
                    _choice(
                        "في المطبخ شفنا 🥄 و 🍽️ — إيه كمان في المطبخ؟",
                        "In the kitchen we saw a spoon and a plate — what else is in the kitchen?",
                        [
                            _opt("r_pan", "مقلاة", "Frying pan", "🍳"),
                            _opt("r_bird", "عصفور", "Bird", "🐦"),
                            _opt("r_boat", "مركب", "Boat", "⛵"),
                        ],
                        "r_pan",
                    ),
                    _choice(
                        "في الحديقة شفنا 🌸 و 🦋 — إيه كمان في الحديقة؟",
                        "In the garden we saw a flower and a butterfly — what else is in the garden?",
                        [
                            _opt("r_tree", "شجرة", "Tree", "🌳"),
                            _opt("r_cup", "فنجان", "Cup", "☕"),
                            _opt("r_shoe", "جزمة", "Shoe", "👟"),
                        ],
                        "r_tree",
                    ),
                    _choice(
                        "شفنا 🐱 و 🐶 — إيه كمان حيوان؟",
                        "We saw a cat and a dog — which of these is an animal too?",
                        [
                            _opt("r_rabbit", "أرنب", "Rabbit", "🐰"),
                            _opt("r_car", "عربية", "Car", "🚗"),
                            _opt("r_chair", "كرسي", "Chair", "🪑"),
                        ],
                        "r_rabbit",
                    ),
                ],
            },
            {
                "name_ar": "نكمّل المجموعة",
                "name_en": "Complete the group",
                "exercises": [
                    _choice(
                        "فواكه 🍎 و 🍌 — مين فاكهة برضه؟",
                        "Apples and bananas are fruit — which of these is fruit too?",
                        [
                            _opt("r_grapes", "عنب", "Grapes", "🍇"),
                            _opt("r_carrot", "جزر", "Carrot", "🥕"),
                            _opt("r_sock", "شراب", "Sock", "🧦"),
                        ],
                        "r_grapes",
                    ),
                    _choice(
                        "هدوم 👕 و 👖 — مين هدوم برضه؟",
                        "A shirt and pants are clothes — which of these is clothing too?",
                        [
                            _opt("r_hat", "قبعة", "Hat", "🧢"),
                            _opt("r_popcorn", "فشار", "Popcorn", "🍿"),
                            _opt("r_bone", "عضم", "Bone", "🦴"),
                        ],
                        "r_hat",
                    ),
                    _choice(
                        "حاجات بنشربها 🥛 و 💧 — إيه كمان بنشربه؟",
                        "Milk and water are drinks — which of these do we drink too?",
                        [
                            _opt("r_juice", "عصير", "Juice", "🧃"),
                            _opt("r_bone", "عضم", "Bone", "🦴"),
                            _opt("r_teddy", "دبدوب", "Teddy", "🧸"),
                        ],
                        "r_juice",
                    ),
                ],
            },
        ],
    },
    {
        # --- Word / naming practice: picture naming (choice) -----------------
        # See a picture (emoji in the prompt), pick the matching WRITTEN word.
        # This is simple WORD-RECOGNITION content ONLY — it is NOT speech
        # therapy and NOT pronunciation training. Real speech/pronunciation
        # practice must be designed with a speech therapist. The choice type
        # already offers the optional mic (reusing the existing speech-answer
        # flow unchanged); that is incidental, not a claim of speech training.
        "key": "picture_naming",
        "category": "cognitive",
        "name_ar": "نسمّي الصور",
        "name_en": "Picture naming",
        "icon": "picture",
        "levels": [
            {
                "name_ar": "إيه ده؟",
                "name_en": "What is this?",
                "exercises": [
                    _choice(
                        "إيه ده؟ 🐱", "What is this? 🐱",
                        [
                            _opt("n_cat", "قطة", "Cat", "قطة"),
                            _opt("n_dog", "كلب", "Dog", "كلب"),
                            _opt("n_book", "كتاب", "Book", "كتاب"),
                        ],
                        "n_cat",
                    ),
                    _choice(
                        "إيه ده؟ ☀️", "What is this? ☀️",
                        [
                            _opt("n_sun", "شمس", "Sun", "شمس"),
                            _opt("n_moon", "قمر", "Moon", "قمر"),
                            _opt("n_door", "باب", "Door", "باب"),
                        ],
                        "n_sun",
                    ),
                    _choice(
                        "إيه ده؟ 🍎", "What is this? 🍎",
                        [
                            _opt("n_apple", "تفاحة", "Apple", "تفاحة"),
                            _opt("n_orange", "برتقالة", "Orange", "برتقالة"),
                            _opt("n_ball", "كرة", "Ball", "كرة"),
                        ],
                        "n_apple",
                    ),
                ],
            },
            {
                "name_ar": "إيه ده؟ كمان",
                "name_en": "What is this? More",
                "exercises": [
                    _choice(
                        "إيه ده؟ ⚽", "What is this? ⚽",
                        [
                            _opt("n_ball", "كرة", "Ball", "كرة"),
                            _opt("n_apple", "تفاحة", "Apple", "تفاحة"),
                            _opt("n_cat", "قطة", "Cat", "قطة"),
                        ],
                        "n_ball",
                    ),
                    _choice(
                        "إيه ده؟ 🏠", "What is this? 🏠",
                        [
                            _opt("n_house", "بيت", "House", "بيت"),
                            _opt("n_tree", "شجرة", "Tree", "شجرة"),
                            _opt("n_car", "عربية", "Car", "عربية"),
                        ],
                        "n_house",
                    ),
                    _choice(
                        "إيه ده؟ 🥛", "What is this? 🥛",
                        [
                            _opt("n_milk", "لبن", "Milk", "لبن"),
                            _opt("n_water", "ميّة", "Water", "ميّة"),
                            _opt("n_bread", "عيش", "Bread", "عيش"),
                        ],
                        "n_milk",
                    ),
                ],
            },
        ],
    },
]


def seed(reset: bool = False) -> None:
    if reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    db = SessionLocal()
    try:
        for order, sk in enumerate(CURRICULUM):
            skill = db.scalar(select(Skill).where(Skill.key == sk["key"]))
            if skill is None:
                skill = Skill(
                    key=sk["key"],
                    category=sk["category"],
                    name_ar=sk["name_ar"],
                    name_en=sk["name_en"],
                    icon=sk["icon"],
                    order=order,
                )
                db.add(skill)
                db.flush()

            # Level-granular idempotency: existing skills (e.g. on a real
            # tifl.db) pick up any newly added levels without being touched;
            # a level that already exists is left alone so re-seeding never
            # duplicates exercises.
            existing_levels = {lv.level for lv in skill.levels}
            for lvl_index, lvl in enumerate(sk["levels"], start=1):
                if lvl_index in existing_levels:
                    continue
                level = SkillLevel(
                    skill_id=skill.id,
                    level=lvl_index,
                    name_ar=lvl["name_ar"],
                    name_en=lvl["name_en"],
                )
                db.add(level)
                db.flush()
                for ex in lvl["exercises"]:
                    db.add(
                        Exercise(
                            skill_level_id=level.id,
                            type=ex["type"],
                            prompt_ar=ex["prompt_ar"],
                            prompt_en=ex["prompt_en"],
                            options=ex["options"],
                            correct_option_id=ex["correct_option_id"],
                        )
                    )
        db.commit()
        skills = db.scalars(select(Skill)).all()
        print(f"Seeded {len(skills)} skills.")
    finally:
        db.close()


if __name__ == "__main__":
    import sys

    seed(reset="--reset" in sys.argv)
