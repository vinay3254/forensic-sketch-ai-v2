import json

from backend.ai.schemas import Attributes, Coverage, Edit, EditPlan
from backend.cases.details import CaseDetails

ATTRIBUTE_SYSTEM_PROMPT = (
    "You convert a witness's description of a person's face into structured attributes. "
    "Reply with exactly one JSON object and nothing else. It must match this JSON schema:\n"
    f"{json.dumps(Attributes.model_json_schema())}\n"
    "Use short descriptive phrases (e.g. \"broad, slightly hooked\"). "
    "Set a field to null when the witness did not mention it. Never invent features."
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


def build_coverage_request(free_recall: str, features: dict[str, str]) -> str:
    keys = "\n".join(f"{k}: {label}" for k, label in features.items())
    return f"Features:\n{keys}\n\nWitness's free account:\n{free_recall}"


def build_image_prompt(a: Attributes) -> str:
    who = " ".join(x for x in [a.age_range, a.gender or "person"] if x)
    parts = [f"Quick hand-drawn composite pencil sketch of a {who}, front view"]
    features = [
        f"{a.skin_tone} skin" if a.skin_tone else None,
        f"{a.face_shape} face" if a.face_shape else None,
        f"{a.jaw} jaw" if a.jaw else None,
        f"{a.eyes} eyes" if a.eyes else None,
        f"{a.eyebrows} eyebrows" if a.eyebrows else None,
        f"{a.nose} nose" if a.nose else None,
        a.mouth,
        f"{a.ears} ears" if a.ears else None,
        a.hair,
        a.facial_hair,
        a.marks,
        a.accessories,
    ]
    features = [f for f in features if f]
    if features:
        parts[0] += " with " + ", ".join(features)
    parts.append(
        "Drawn by hand by a forensic artist in about twenty minutes, in soft pencil on plain off-white paper: "
        "loose dark outlines, rough hatching for shadows, hair drawn as simple shaded shapes rather than single "
        "strands, no skin texture, not photorealistic, slight natural asymmetry. An ordinary, average-looking "
        "face, not idealised and not a model. Black and white only, no colour. Neutral expression, looking "
        "straight ahead, head and shoulders, plain shirt collar, plain background."
    )
    return ". ".join(parts)


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


def build_body_prompt(a: Attributes, d: CaseDetails) -> str:
    """Only the person's look goes in; incident details (weapon, offence...) never do."""
    who = " ".join(x for x in [a.age_range, a.gender] if x) or "adult person"
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
