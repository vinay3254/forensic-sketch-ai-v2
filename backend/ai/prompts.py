import json
import re

from backend.ai.schemas import Attributes, Coverage, Edit, EditPlan, FigureEdit, Translation
from backend.cases.details import CaseDetails

ATTRIBUTE_SYSTEM_PROMPT = (
    "You convert a witness's description of a person's face into structured attributes. "
    "Reply with exactly one JSON object and nothing else. It must match this JSON schema:\n"
    f"{json.dumps(Attributes.model_json_schema())}\n"
    "Use short descriptive phrases (e.g. \"broad, slightly hooked\"). "
    "Set a field to null when the witness did not mention it. Never invent features. "
    "appearance is the ethnic or regional look the witness named (e.g. \"South Indian\"); never infer it "
    "from skin colour or any other feature."
)

EDIT_SYSTEM_PROMPT = (
    "You help a witness refine a face portrait. Given the current attributes and the witness's request, "
    "decide which facial regions to change. Reply with exactly one JSON object and nothing else. "
    "It must match this JSON schema:\n"
    f"{json.dumps(EditPlan.model_json_schema())}\n"
    "Each edit's change is a short phrase describing the new look of that region. "
    "reply is one friendly sentence to the officer saying what you changed. "
    "If the request is too vague to act on, return no edits, set needs_clarification to true, "
    "and use reply to ask one specific question."
)

COVERAGE_SYSTEM_PROMPT = (
    "You help an officer during a witness interview. Given the witness's free account and a list of facial "
    "features (key: label), find the parts of the account that already describe each feature. "
    "Reply with exactly one JSON object and nothing else. It must match this JSON schema:\n"
    f"{json.dumps(Coverage.model_json_schema())}\n"
    "Each quote must be copied character for character from the account: same words, spelling, case and "
    "punctuation. Never paraphrase, correct, summarise or combine separate parts. Use only the given keys. "
    "Leave a feature out if the account does not mention it. Never guess."
)


TRANSLATE_SYSTEM_PROMPT = (
    "You translate a witness's spoken description of a person into English for a police record. "
    "Reply with exactly one JSON object and nothing else. It must match this JSON schema:\n"
    f"{json.dumps(Translation.model_json_schema())}\n"
    "Translate faithfully and literally. Keep every detail and every sign of doubt (\"maybe\", \"I think\"), "
    "keep the witness's order, and keep numbers, names and English words as spoken. Never add, remove, "
    "summarise, correct or explain anything. Text that is already English stays as it is."
)


FIGURE_SYSTEM_PROMPT = (
    "You adjust a 3D mannequin of a person for an officer, from their request. Current settings come as JSON: "
    "height_cm (120-220), build (0 slim .. 1 obese), muscle (0..1), gender (0 male .. 1 female), age (years), "
    "top (none, tshirt, shirt, hoodie, jacket, kurta), bottom (none, trousers, jeans, shorts, skirt), "
    "headwear (none, cap). Reply with exactly one JSON object and nothing else, matching this JSON schema:\n"
    f"{json.dumps(FigureEdit.model_json_schema())}\n"
    "changes holds only the settings the request changes, with their new values; relative requests "
    "(\"a bit heavier\", \"taller\") move the current value by a sensible step. Clothing not in the lists "
    "maps to the closest item. reply is one short sentence saying what changed."
)


def build_coverage_request(free_recall: str, features: dict[str, str]) -> str:
    keys = "\n".join(f"{k}: {label}" for k, label in features.items())
    return f"Features:\n{keys}\n\nWitness's free account:\n{free_recall}"


FEATURE_LABELS = [
    ("gender", "Gender"), ("age_range", "Age"), ("appearance", "Ethnic appearance"),
    ("skin_tone", "Skin"), ("face_shape", "Face shape"), ("jaw", "Jaw"),
    ("eyes", "Eyes"), ("eyebrows", "Eyebrows"), ("nose", "Nose"), ("mouth", "Mouth"), ("ears", "Ears"),
    ("hair", "Hair"), ("facial_hair", "Facial hair"), ("marks", "Marks"), ("accessories", "Accessories"),
    ("notes", "Other details"),
]

# witness wording can name the incident; image prompts must not, so these become neutral words
_CRIME_WORDS = re.compile(
    r"\b(suspects?|criminals?|mugshots?|thie(?:f|ves)|robbers?|burglars?|attackers?|assailants?|offenders?|"
    r"culprits?|murderers?|killers?|kidnappers?|accused|perpetrators?|police)\b",
    re.I,
)


def scrub(text: str) -> str:
    return _CRIME_WORDS.sub("person", text)


def build_image_prompt(a: Attributes, description: str | None = None) -> str:
    """The first sketch: every described feature by name, plus the witness's own words when typed in
    directly (an interview passes none, so "don't know" features stay blank)."""
    lines = ["Quick hand-drawn composite pencil sketch of one person's face, front view, drawn from a witness description."]
    features = [f"{label}: {getattr(a, key)}." for key, label in FEATURE_LABELS if getattr(a, key)]
    if features:
        lines.append(" ".join(features))
    if description and description.strip():
        lines.append(f'The witness described the face as: "{scrub(description.strip())}"')
    lines.append(
        "Left and right always mean the person's own left and right, not the viewer's: the person's own left "
        "cheek appears on the right side of the drawing."
    )
    lines.append(
        "Drawn by hand by a forensic artist in about twenty minutes, in soft pencil on plain off-white paper: "
        "loose dark outlines, rough hatching for shadows, hair drawn as simple shaded shapes rather than single "
        "strands, no skin texture, not photorealistic, slight natural asymmetry. Draw exactly the face described, "
        "neither more nor less attractive than the description says. Black and white only, "
        "no colour. Neutral expression, looking straight ahead, head and shoulders, plain shirt collar, plain background."
    )
    return " ".join(lines)


def build_style_prompt(category: str, change: str) -> str:
    """One style from the library (or typed by the officer) put on the existing sketch."""
    return (
        f"Edit this black and white pencil sketch. Change only the {category.lower()}: the person is now "
        f"{scrub(change.strip())}. Keep the same person, identity, face, expression, pose, framing, rough "
        "hand-drawn pencil line style and plain background exactly the same, and change nothing else. "
        "Black and white only."
    )


def build_edit_prompt(edits: list[Edit]) -> str:
    changes = "; ".join(f"{e.region.replace('_', ' ')}: {e.change}" for e in edits)
    return (
        f"Edit this black and white pencil sketch. Change only the following: {changes}. "
        "Keep the same person, identity, pose, expression, framing, rough hand-drawn pencil line style, "
        "plain background "
        "and every other facial feature, including facial hair, exactly the same. Black and white only."
    )


# disguise variants: kind -> (label, change, regions to localize; None = the whole sketch may change)
VARIANTS: dict[str, tuple[str, str, list[str] | None]] = {
    "cap": ("Cap", "wearing a plain baseball cap", ["hair"]),
    "brimmed_hat": ("Brimmed hat", "wearing a plain hat with a wide brim", ["hair"]),
    "hood": ("Hood", "wearing a hooded top with the hood up over the head", None),
    "glasses": ("Glasses", "wearing plain thin-framed glasses", ["accessories", "eyes"]),
    "sunglasses": ("Sunglasses", "wearing dark sunglasses", ["accessories", "eyes"]),
    "moustache": ("Moustache", "with a full moustache", ["facial_hair"]),
    "full_beard": ("Full beard", "with a full beard and moustache", ["facial_hair"]),
    "goatee": ("Goatee", "with a goatee on the chin", ["facial_hair"]),
    "stubble": ("Stubble", "with a few days of stubble", ["facial_hair"]),
    "shaved_head": ("Shaved head", "with a fully shaved head", ["hair"]),
}


def build_variant_prompt(kind: str) -> str:
    return (
        f"Edit this black and white pencil sketch to show the same person {VARIANTS[kind][1]}. "
        "Keep the same person, identity, face, expression, pose, framing, rough hand-drawn pencil line style "
        "and plain background exactly the same, and change nothing else. Black and white only."
    )


def build_body_prompt(a: Attributes, d: CaseDetails, from_sketch: bool = False) -> str:
    """Only the person's look goes in; incident details (weapon, offence...) never do.
    With `from_sketch` the face sketch is the input image, so the figure keeps that face."""
    who = " ".join(x for x in [a.age_range, a.gender] if x) or "adult person"
    if from_sketch:
        parts = [
            "Extend this head-and-shoulders pencil sketch into a full-length standing figure of the same person. "
            "Keep the same face, identity, hairstyle, earrings, marks and other details exactly as drawn, "
            "and the same rough hand-drawn pencil style"
        ]
    else:
        parts = [f"Quick hand-drawn pencil sketch of a full-length standing figure of a {who}"]
    head = ", ".join(x for x in [a.hair, a.facial_hair] if x)
    if head:
        parts.append(f"Head as in the face sketch: {head}")
    if d.build:
        parts.append(f"Body build as the witness described it: {d.build}")
    if d.clothing:
        parts.append(f"Wearing: {d.clothing}")
    parts.append(
        "Drawn by hand in soft pencil on plain off-white paper: loose outlines, rough hatching, the face drawn "
        "simply. Front view, standing straight with arms relaxed at the sides, the whole body visible from head "
        "to feet, plain background. Black and white only, no colour."
    )
    return ". ".join(parts)


def build_photo_prompt(a: Attributes) -> str:
    # the sketch carries shape but no colour, so colours come from the witness's attributes
    colours = [
        f"ethnic appearance: {a.appearance}" if a.appearance else None,
        f"{a.skin_tone} skin" if a.skin_tone else None,
        f"eyes: {a.eyes}" if a.eyes else None,
        f"hair: {a.hair}" if a.hair else None,
        f"facial hair: {a.facial_hair}" if a.facial_hair else None,
    ]
    colours = [c for c in colours if c]
    prompt = (
        "Turn this black and white pencil sketch into a realistic colour photograph of the same person. "
        "Keep the identity, face shape, every facial feature, proportions, pose, expression and framing "
        "exactly as drawn. Front-facing, head and shoulders, plain light-grey background, even soft lighting, "
        "natural skin texture, sharp focus."
    )
    if colours:
        prompt += " Colours from the witness description: " + "; ".join(colours) + "."
    return prompt


def apply_edits(a: Attributes, edits: list[Edit]) -> Attributes:
    data = a.model_dump()
    for e in edits:
        old = data.get(e.region)
        data[e.region] = f"{old}, {e.change}" if old else e.change
    return Attributes(**data)
