import base64
from types import SimpleNamespace

import pytest

from backend.ai.client import LiveAIClient, extract_json
from backend.ai.mock import MockAIClient
from backend.ai.prompts import apply_edits, build_edit_prompt, build_image_prompt
from backend.ai.schemas import Attributes, Edit
from backend.errors import AppError


def test_image_prompt_skips_nulls_and_has_no_crime_words():
    p = build_image_prompt(Attributes(gender="male", age_range="30-35", nose="broad"))
    assert "30-35 male" in p and "broad nose" in p and "None" not in p
    for w in ("suspect", "criminal", "mugshot"):
        assert w not in p.lower()


def test_edit_prompt_lists_changes_and_preserves_identity():
    p = build_edit_prompt([Edit(region="jaw", change="wider")])
    assert "jaw: wider" in p and "same person" in p


def test_apply_edits_appends_to_existing_value():
    a = apply_edits(Attributes(jaw="square"), [Edit(region="jaw", change="wider")])
    assert a.jaw == "square, wider"


def test_extract_json_handles_fences_and_prose():
    assert extract_json('Sure!\n```json\n{"gender": "male"}\n```') == {"gender": "male"}


class FakeChat:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), 0

    def create(self, **kw):
        self.calls += 1
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.replies.pop(0)))])


def fake_openai(chat=None, images=None):
    return SimpleNamespace(chat=SimpleNamespace(completions=chat), images=images)


def test_parse_edit_rejects_unknown_region_then_retries(settings):
    chat = FakeChat(
        [
            '{"edits":[{"region":"tattoo","change":"x"}],"reply":"ok"}',
            '{"edits":[{"region":"nose","change":"smaller"}],"reply":"ok"}',
        ]
    )
    plan = LiveAIClient(settings, fake_openai(chat)).parse_edit("smaller nose", Attributes())
    assert plan.edits[0].region == "nose" and chat.calls == 2


def test_parse_fails_after_one_retry(settings):
    chat = FakeChat(["not json", "still not json"])
    with pytest.raises(AppError) as e:
        LiveAIClient(settings, fake_openai(chat)).extract_attributes("tall man")
    assert e.value.code == "AI_PARSE_FAILED" and chat.calls == 2


def test_generate_image_accepts_b64(settings):
    png = b"\x89PNG fake"
    images = SimpleNamespace(
        generate=lambda **kw: SimpleNamespace(
            data=[SimpleNamespace(b64_json=base64.b64encode(png).decode(), url=None)]
        )
    )
    assert LiveAIClient(settings, fake_openai(images=images)).generate_image("p") == png


def test_generate_image_accepts_url(settings, monkeypatch):
    images = SimpleNamespace(
        generate=lambda **kw: SimpleNamespace(data=[SimpleNamespace(b64_json=None, url="http://img/x.png")])
    )
    monkeypatch.setattr(
        "backend.ai.client.httpx.get",
        lambda url, timeout: SimpleNamespace(content=b"bytes", raise_for_status=lambda: None),
    )
    assert LiveAIClient(settings, fake_openai(images=images)).generate_image("p") == b"bytes"


def test_mock_gender_uses_whole_words():
    assert MockAIClient().extract_attributes("a woman, female, 40s").gender == "female"
    assert MockAIClient().extract_attributes("male in his 30s").gender == "male"


def test_mock_unclear_edit_needs_clarification():
    assert MockAIClient().parse_edit("hmm not quite", Attributes()).needs_clarification is True
