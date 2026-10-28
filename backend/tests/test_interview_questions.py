"""The interview prompt bank must stay neutral: no question may suggest an answer."""

import re

import pytest

from backend.interview.questions import EXTRAS, FEATURES, FREE_RECALL, all_prompts

YES_NO_STARTS = ("was", "were", "did", "do", "does", "is", "are", "had", "has", "have", "could", "would")
SUGGESTIVE_WORDS = {
    "dark", "light", "fair", "pale", "big", "large", "small", "little", "long", "short", "round", "oval",
    "square", "thick", "thin", "wide", "narrow", "black", "brown", "white", "grey", "gray", "blond",
    "blonde", "red", "tall", "old", "young", "beard", "moustache", "mustache", "scar", "tattoo",
}


@pytest.mark.parametrize("prompt", all_prompts())
def test_prompt_is_not_a_yes_no_question(prompt):
    assert prompt.split()[0].lower().strip(",") not in YES_NO_STARTS


@pytest.mark.parametrize("prompt", all_prompts())
def test_prompt_offers_no_alternatives(prompt):
    assert " or " not in prompt.lower()


@pytest.mark.parametrize("prompt", all_prompts())
def test_prompt_suggests_no_value(prompt):
    words = set(re.findall(r"[a-z]+", prompt.lower()))
    assert not words & SUGGESTIVE_WORDS, words & SUGGESTIVE_WORDS


def test_bank_covers_the_spec_sections():
    assert FREE_RECALL["key"] == "free_recall"
    assert [f["key"] for f in FEATURES] == [
        "age_gender", "appearance", "skin_tone", "face_shape", "eyes", "eyebrows", "nose", "mouth", "ears", "jaw_chin",
    ]
    assert [e["key"] for e in EXTRAS] == [
        "facial_hair", "hairstyle", "glasses_accessories", "distinguishing_features",
        "height", "build", "clothing", "movement", "voice",
    ]
    assert all(e["optional"] for e in EXTRAS) and not any(f["optional"] for f in FEATURES)


def test_questions_endpoint_returns_the_bank(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    body = client.get("/api/interview/questions").json()
    assert body["free_recall"] == FREE_RECALL
    assert body["features"] == FEATURES and body["extras"] == EXTRAS


def test_questions_endpoint_needs_login(client):
    r = client.get("/api/interview/questions")
    assert r.status_code == 401 and r.json()["error"]["code"] == "UNAUTHENTICATED"


def test_appearance_answer_fills_the_appearance_attribute():
    from backend.interview.transcript import FIELDS_FOR

    assert FIELDS_FOR["appearance"] == ("appearance",)
