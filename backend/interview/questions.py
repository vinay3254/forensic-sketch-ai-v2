"""Fixed interview prompts, read aloud by the officer.

Every prompt is open and neutral: it names the feature but never suggests a value,
offers alternatives, or invites a yes/no answer. Nothing here is generated at runtime,
so no wording can drift. Tests in test_interview_questions.py enforce the rules.
"""

FREE_RECALL = {
    "key": "free_recall",
    "label": "Free account",
    "prompt": "Take your time. In your own words, describe the person's face. Anything you remember, even details that seem unimportant.",
    "guidance": "Let the witness speak without interrupting. Do not ask follow-up questions in this step.",
}


def _q(key: str, label: str, prompt: str, optional: bool = False) -> dict:
    return {"key": key, "label": label, "prompt": prompt, "optional": optional}


FEATURES = [
    _q("age_gender", "Age and gender", "What can you tell me about the person's age and gender, if you remember?"),
    _q("skin_tone", "Skin", "Describe the person's skin, if you remember it."),
    _q("face_shape", "Face shape", "Describe the overall shape of the person's face, if you remember it."),
    _q("eyes", "Eyes", "Describe the person's eyes, if you remember them."),
    _q("eyebrows", "Eyebrows", "Describe the person's eyebrows, if you remember them."),
    _q("nose", "Nose", "Describe the person's nose, if you remember it."),
    _q("mouth", "Mouth and lips", "Describe the person's mouth and lips, if you remember them."),
    _q("ears", "Ears", "Describe the person's ears, if you remember them."),
    _q("jaw_chin", "Jaw and chin", "Describe the person's jaw and chin, if you remember them."),
]

EXTRAS = [
    _q("facial_hair", "Facial hair", "What, if anything, do you remember about hair on the person's face?", optional=True),
    _q("hairstyle", "Hairstyle", "Describe the hair on the person's head, if you remember it.", optional=True),
    _q(
        "glasses_accessories",
        "Glasses and accessories",
        "What, if anything, do you remember the person wearing on their head and face?",
        optional=True,
    ),
    _q(
        "distinguishing_features",
        "Distinguishing features",
        "What, if anything, stood out to you about the person's face?",
        optional=True,
    ),
]


def all_prompts() -> list[str]:
    return [FREE_RECALL["prompt"]] + [q["prompt"] for q in FEATURES + EXTRAS]


PROMPTS = {q["key"]: q["prompt"] for q in FEATURES + EXTRAS}
