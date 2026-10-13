"""LLM question drafting: validation, human-in-the-loop (drafts are not saved), access control, failure modes.
The Groq call (`_chat`) is always replaced -- these tests never touch the network."""
import json

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.modules.question_bank import llm_generation

GOOD = {
    "question_type": "multiple_choice", "prompt": "What is 2 + 3?", "difficulty": "easy",
    "content": {"choices": [{"id": "a", "text": "4"}, {"id": "b", "text": "5"}], "correct_choice_id": "b"},
}
TF = {"question_type": "true_false", "prompt": "5 is prime.", "difficulty": "medium", "content": {"correct_answer": True}}
BAD_CHOICE = {  # correct_choice_id points at a choice that does not exist
    "question_type": "multiple_choice", "prompt": "Broken", "difficulty": "easy",
    "content": {"choices": [{"id": "a", "text": "x"}, {"id": "b", "text": "y"}], "correct_choice_id": "z"},
}
BAD_SHAPE = {"question_type": "text_input", "prompt": "Mismatch", "difficulty": "easy", "content": {"correct_answer": True}}


@pytest.fixture
def llm(monkeypatch):
    """Turns the feature on and lets a test set what the 'model' answers."""
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-key")
    reply = {"raw": json.dumps({"questions": [GOOD, TF]})}

    async def fake_chat(system, user):
        reply["system"], reply["user"] = system, user
        return reply["raw"]

    monkeypatch.setattr(llm_generation, "_chat", fake_chat)
    return reply


def request_body(skill_id, **kw):
    return {"skill_id": skill_id, "count": 5, "difficulty": "mixed", **kw}


@pytest.mark.asyncio
async def test_instructor_gets_validated_drafts_and_nothing_is_saved(client, instructor, skill_id, llm):
    res = await client.post("/question-bank/generate", json=request_body(skill_id, topic="addition"), headers=instructor[0])
    assert res.status_code == 200, res.text
    body = res.json()
    assert [d["prompt"] for d in body["drafts"]] == ["What is 2 + 3?", "5 is prime."]
    assert body["drafts"][0]["tags"] == ["ai-generated"] and body["drafts"][0]["skill_id"] == skill_id
    assert body["discarded"] == 0
    assert "addition" in llm["user"]  # the instructor's topic reached the prompt
    assert (await client.get(f"/question-bank/questions?skill_id={skill_id}", headers=instructor[0])).json() == []  # drafts only


@pytest.mark.asyncio
async def test_invalid_model_output_is_discarded_not_returned(client, instructor, skill_id, llm):
    llm["raw"] = json.dumps({"questions": [GOOD, BAD_CHOICE, BAD_SHAPE, "not an object"]})
    body = (await client.post("/question-bank/generate", json=request_body(skill_id), headers=instructor[0])).json()
    assert [d["prompt"] for d in body["drafts"]] == ["What is 2 + 3?"]
    assert body["discarded"] == 3


@pytest.mark.asyncio
async def test_requested_difficulty_overrides_the_models_label(client, instructor, skill_id, llm):
    body = (await client.post("/question-bank/generate", json=request_body(skill_id, difficulty="hard"), headers=instructor[0])).json()
    assert {d["difficulty"] for d in body["drafts"]} == {"hard"}


@pytest.mark.asyncio
async def test_count_caps_the_number_of_drafts(client, instructor, skill_id, llm):
    body = (await client.post("/question-bank/generate", json=request_body(skill_id, count=1), headers=instructor[0])).json()
    assert len(body["drafts"]) == 1 and body["discarded"] == 1


@pytest.mark.asyncio
async def test_unreadable_model_answer_is_a_502(client, instructor, skill_id, llm):
    llm["raw"] = "sorry, I cannot do that"
    res = await client.post("/question-bank/generate", json=request_body(skill_id), headers=instructor[0])
    assert res.status_code == 502


@pytest.mark.asyncio
async def test_not_configured_is_a_503(client, instructor, skill_id, monkeypatch):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")  # whatever a developer keeps in .env
    res = await client.post("/question-bank/generate", json=request_body(skill_id), headers=instructor[0])
    assert res.status_code == 503


@pytest.mark.asyncio
async def test_only_instructors_may_generate(client, student, skill_id, llm):
    assert (await client.post("/question-bank/generate", json=request_body(skill_id))).status_code == 401
    assert (await client.post("/question-bank/generate", json=request_body(skill_id), headers=student[0])).status_code == 403


@pytest.mark.asyncio
async def test_unknown_skill_and_bad_count_are_rejected(client, instructor, llm):
    missing = "00000000-0000-0000-0000-000000000000"
    assert (await client.post("/question-bank/generate", json=request_body(missing), headers=instructor[0])).status_code == 404
    assert (await client.post("/question-bank/generate", json=request_body(missing, count=50), headers=instructor[0])).status_code == 422


@pytest.mark.asyncio
async def test_groq_outage_is_a_502_not_a_crash(monkeypatch):
    import httpx

    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-key")

    class Boom:
        def __init__(self, *a, **k): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): ...
        async def post(self, *a, **k): raise httpx.ConnectError("down")

    monkeypatch.setattr(llm_generation.httpx, "AsyncClient", Boom)
    with pytest.raises(HTTPException) as err:
        await llm_generation._chat("s", "u")
    assert err.value.status_code == 502
