"""Witnesses speak in their own language: the words are kept verbatim, an English translation is
stored beside them, and the sketch is made from the English."""

import pytest

from backend.interview.transcript import canonical_transcript, render_description


@pytest.fixture
def case_id(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    return client.post("/api/cases", json={"title": "t"}).json()["id"]


def new_interview(client, case_id):
    return client.post(f"/api/cases/{case_id}/interviews").json()["id"]


def put(client, case_id, iid, **draft):
    return client.put(f"/api/cases/{case_id}/interviews/{iid}", json=draft)


KN = "ಕಣ್ಣುಗಳು ದೊಡ್ಡದಾಗಿದ್ದವು"


def test_translate_returns_english_and_is_audited(client, case_id, login):
    r = client.post(f"/api/cases/{case_id}/translate", json={"text": KN, "lang": "kn-IN"})
    assert r.status_code == 200 and r.json()["english"]
    login(client, "admin", "adminpass")
    rows = client.get(f"/api/audit?action=translate&case_id={case_id}").json()["items"]
    assert rows[0]["detail"] == {"lang": "kn-IN", "chars": len(KN)}


def test_supported_languages(client, case_id):
    for code in ("hi-IN", "kn-IN", "te-IN", "ta-IN", "ml-IN", "mr-IN", "bn-IN", "gu-IN"):
        assert client.post(f"/api/cases/{case_id}/translate", json={"text": "x", "lang": code}).status_code == 200
    assert client.post(f"/api/cases/{case_id}/translate", json={"text": "x", "lang": "xx-XX"}).status_code == 422


def test_english_needs_no_translation(app, client, case_id):
    app.state.ai_client.translate = lambda text, language: pytest.fail("no AI call for English")
    r = client.post(f"/api/cases/{case_id}/translate", json={"text": "big eyes", "lang": "en-IN"})
    assert r.json()["english"] == "big eyes"


def test_ai_translation_failure_is_503(app, client, case_id):
    from backend.errors import AppError

    def boom(text, language):
        raise AppError("AI_UNAVAILABLE", "down", 503)

    app.state.ai_client.translate = boom
    assert client.post(f"/api/cases/{case_id}/translate", json={"text": KN, "lang": "kn-IN"}).status_code == 503


def test_draft_keeps_the_original_words_language_and_translation(client, case_id):
    iid = new_interview(client, case_id)
    r = put(client, case_id, iid, free_recall=KN, free_recall_source="speech", free_recall_lang="kn-IN",
            free_recall_english="The eyes were big",
            answers=[{"key": "eyes", "answer": KN, "status": "remembered", "source": "speech",
                      "lang": "kn-IN", "english": "The eyes were big"}])
    iv = r.json()
    assert iv["free_recall"] == KN and iv["free_recall_lang"] == "kn-IN" and iv["free_recall_english"] == "The eyes were big"
    assert iv["answers"][0]["answer"] == KN and iv["answers"][0]["english"] == "The eyes were big"


def test_english_answers_store_no_language_fields(client, case_id):
    """Old transcripts must hash exactly as before."""
    iid = new_interview(client, case_id)
    iv = put(client, case_id, iid, free_recall="tall man", answers=[
        {"key": "eyes", "answer": "big", "status": "remembered", "lang": "en-IN", "english": "ignored"},
    ]).json()
    assert set(iv["answers"][0]) == {"key", "prompt", "answer", "status", "source"}
    assert "lang" not in canonical_transcript(iv) and "english" not in canonical_transcript(iv)


def test_unsupported_answer_language_is_rejected(client, case_id):
    iid = new_interview(client, case_id)
    r = put(client, case_id, iid, answers=[{"key": "eyes", "answer": "x", "lang": "xx-XX"}])
    assert r.status_code == 422


def test_untranslated_words_block_confirmation(client, case_id):
    iid = new_interview(client, case_id)
    put(client, case_id, iid, answers=[{"key": "eyes", "answer": KN, "status": "remembered", "lang": "kn-IN"}])
    r = client.post(f"/api/cases/{case_id}/interviews/{iid}/confirm", json={"witness_confirmed": True})
    assert r.status_code == 422 and r.json()["error"]["code"] == "TRANSLATION_MISSING"


def test_hash_covers_the_translation(client, case_id):
    iid = new_interview(client, case_id)
    iv = put(client, case_id, iid, answers=[
        {"key": "eyes", "answer": KN, "status": "remembered", "lang": "kn-IN", "english": "big eyes"},
    ]).json()
    text = canonical_transcript(iv)
    assert "big eyes" in text and "kn-IN" in text and KN in text


def test_description_for_the_sketch_uses_the_english():
    iv = {"free_recall": KN, "free_recall_lang": "kn-IN", "free_recall_english": "A tall man",
          "answers": [{"key": "eyes", "answer": KN, "status": "uncertain", "lang": "kn-IN", "english": "big eyes"}]}
    d = render_description(iv)
    assert 'Free account: "A tall man" (translated from Kannada)' in d
    assert 'Eyes (uncertain): "big eyes" (translated from Kannada)' in d
    assert KN not in d


def test_typed_description_in_another_language_is_translated_before_the_sketch(app, client, case_id):
    seen = []
    app.state.ai_client.translate = lambda text, language: (seen.append(language), "male, thick moustache")[1]
    v = client.post(f"/api/cases/{case_id}/generate", json={"description": KN, "lang": "kn-IN"}).json()
    assert seen == ["Kannada"]
    assert v["attributes"]["gender"] == "male" and v["attributes"]["facial_hair"]
    assert v["instruction"] == f"{KN}\n(Kannada) → male, thick moustache"
