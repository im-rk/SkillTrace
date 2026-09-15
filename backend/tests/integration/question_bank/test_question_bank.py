import json
import pytest
from httpx import AsyncClient

from app.modules.iam.models import UserRole


@pytest.fixture
async def instructor_headers(make_user):
    headers, _ = await make_user(UserRole.instructor)
    return headers


@pytest.fixture
async def student_headers(make_user):
    headers, _ = await make_user(UserRole.student)
    return headers


def mcq_payload(skill_id: str, **overrides) -> dict:
    payload = {
        "skill_id": skill_id,
        "question_type": "multiple_choice",
        "prompt": "What is 2 + 2?",
        "difficulty": "easy",
        "content": {
            "choices": [{"id": "a", "text": "3"}, {"id": "b", "text": "4"}],
            "correct_choice_id": "b",
        },
        "tags": ["arithmetic"],
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_case_1_create_valid_mcq(client: AsyncClient, instructor_headers, skill_id):
    response = await client.post("/question-bank/questions", json=mcq_payload(skill_id), headers=instructor_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["content"]["correct_choice_id"] == "b"
    assert data["version"] == 1
    assert data["tags"] == ["arithmetic"]


@pytest.mark.asyncio
async def test_case_2_mcq_correct_choice_id_mismatch(client: AsyncClient, instructor_headers, skill_id):
    payload = mcq_payload(skill_id, content={
        "choices": [{"id": "a", "text": "3"}, {"id": "b", "text": "4"}],
        "correct_choice_id": "c",
    })
    response = await client.post("/question-bank/questions", json=payload, headers=instructor_headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_case_3_mcq_single_choice_rejected(client: AsyncClient, instructor_headers, skill_id):
    payload = mcq_payload(skill_id, content={
        "choices": [{"id": "a", "text": "3"}],
        "correct_choice_id": "a",
    })
    response = await client.post("/question-bank/questions", json=payload, headers=instructor_headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_case_4_create_valid_true_false(client: AsyncClient, instructor_headers, skill_id):
    payload = mcq_payload(
        skill_id,
        question_type="true_false",
        content={"correct_answer": True},
    )
    response = await client.post("/question-bank/questions", json=payload, headers=instructor_headers)
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_case_5_create_valid_text_input(client: AsyncClient, instructor_headers, skill_id):
    payload = mcq_payload(
        skill_id,
        question_type="text_input",
        content={"correct_answer": "Paris", "case_sensitive": False},
    )
    response = await client.post("/question-bank/questions", json=payload, headers=instructor_headers)
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_case_6_non_instructor_forbidden(client: AsyncClient, student_headers, skill_id):
    response = await client.post("/question-bank/questions", json=mcq_payload(skill_id), headers=student_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_case_7_edit_increments_version(client: AsyncClient, instructor_headers, skill_id):
    create_res = await client.post("/question-bank/questions", json=mcq_payload(skill_id), headers=instructor_headers)
    question_id = create_res.json()["id"]

    update_res = await client.patch(
        f"/question-bank/questions/{question_id}",
        json={"prompt": "What is 3 + 3?"},
        headers=instructor_headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["version"] == 2


@pytest.mark.asyncio
async def test_case_8_bulk_import_partial_success(client: AsyncClient, instructor_headers, skill_id):
    rows = []
    for i in range(18):
        rows.append({
            "question_type": "true_false",
            "prompt": f"Statement {i}",
            "difficulty": "easy",
            "content": json.dumps({"correct_answer": True}),
        })
    rows.append({"question_type": "bogus_type", "prompt": "Bad", "difficulty": "easy", "content": "{}"})
    rows.append({"question_type": "true_false", "prompt": "Bad content", "difficulty": "easy", "content": "not json"})

    response = await client.post(
        "/question-bank/bulk-import",
        json={"skill_id": skill_id, "rows": rows},
        headers=instructor_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_rows"] == 20
    assert data["succeeded"] == 18
    assert data["failed"] == 2
    failed_rows = [r["row_number"] for r in data["results"] if r["status"] == "failed"]
    assert failed_rows == [19, 20]


@pytest.mark.asyncio
async def test_case_9_bulk_import_empty(client: AsyncClient, instructor_headers, skill_id):
    response = await client.post(
        "/question-bank/bulk-import",
        json={"skill_id": skill_id, "rows": []},
        headers=instructor_headers,
    )
    assert response.status_code == 200
    assert response.json()["total_rows"] == 0


@pytest.mark.asyncio
async def test_bulk_import_csv(client: AsyncClient, instructor_headers, skill_id):
    csv_content = (
        "question_type,prompt,difficulty,content,tags\n"
        'true_false,"Is the sky blue?",easy,"{""correct_answer"": true}",science\n'
        'bogus,"bad row",easy,"{}",\n'
    )
    files = {"file": ("q.csv", csv_content, "text/csv")}
    response = await client.post(
        "/question-bank/bulk-import/csv",
        files=files,
        data={"skill_id": skill_id},
        headers=instructor_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_rows"] == 2
    assert data["succeeded"] == 1
    assert data["failed"] == 1


@pytest.mark.asyncio
async def test_case_10_list_filtered_by_tag(client: AsyncClient, instructor_headers, skill_id):
    await client.post("/question-bank/questions", json=mcq_payload(skill_id, tags=["algebra"]), headers=instructor_headers)
    await client.post("/question-bank/questions", json=mcq_payload(skill_id, tags=["geometry"]), headers=instructor_headers)

    response = await client.get("/question-bank/questions", params={"tags": "algebra"}, headers=instructor_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["tags"] == ["algebra"]


@pytest.mark.asyncio
async def test_case_11_list_filtered_by_skill_and_difficulty(client: AsyncClient, instructor_headers, skill_id):
    await client.post("/question-bank/questions", json=mcq_payload(skill_id, difficulty="hard"), headers=instructor_headers)
    await client.post("/question-bank/questions", json=mcq_payload(skill_id, difficulty="easy"), headers=instructor_headers)

    response = await client.get(
        "/question-bank/questions",
        params={"skill_id": skill_id, "difficulty": "hard"},
        headers=instructor_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["difficulty"] == "hard"
