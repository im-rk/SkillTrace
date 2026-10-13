"""
LLM-assisted question drafting (Groq's OpenAI-compatible chat API).

The model only ever produces DRAFTS: every item is validated against the same schema as a
hand-written question, and the instructor reviews drafts before saving. The LLM never touches
mastery inference -- that stays the exact, auditable BKT core.
"""
import json
import logging
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from pydantic import ValidationError

from app.core.config import settings
from app.modules.question_bank.schemas import GenerateQuestionsResponse, QuestionCreate

logger = logging.getLogger(__name__)

AI_TAG = "ai-generated"

SYSTEM_PROMPT = """You write quiz questions for an adaptive learning platform.
Reply with ONE JSON object: {"questions": [ ... ]}. Each question has exactly these keys:
  "question_type": "multiple_choice" | "true_false" | "text_input"
  "prompt": the question text
  "difficulty": "easy" | "medium" | "hard"
  "content": depends on question_type:
     multiple_choice -> {"choices": [{"id": "a", "text": "..."}, {"id": "b", "text": "..."}, ...2-4 choices with ids a,b,c,d],
                         "correct_choice_id": "<one of the ids>"}
     true_false      -> {"correct_answer": true | false}
     text_input      -> {"correct_answer": "<short answer, a word, number or expression>", "case_sensitive": false}
Rules: exactly one unambiguously correct answer; no trick questions; the correct answer must be factually right;
text_input answers must be short and have one canonical form; mix the question types."""


def _user_prompt(skill_name: str, description: str | None, count: int, difficulty: str, topic: str | None) -> str:
    level = "a mix of easy, medium and hard" if difficulty == "mixed" else f"all {difficulty}"
    lines = [f"Skill: {skill_name}"]
    if description:
        lines.append(f"Skill description: {description}")
    if topic:
        lines.append(f"Focus on: {topic}")
    lines.append(f"Write {count} questions, {level} difficulty.")
    return "\n".join(lines)


async def _chat(system: str, user: str) -> str:
    """One Groq chat completion in JSON mode; returns the message content. Isolated so tests can replace it."""
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            res = await client.post(
                settings.GROQ_API_URL,
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                json={
                    "model": settings.GROQ_MODEL,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.6,
                },
            )
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        logger.exception("Groq request failed")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="The AI service is unavailable, try again")


def parse_drafts(raw: str, skill_id: UUID, difficulty: str, count: int) -> GenerateQuestionsResponse:
    try:
        items = json.loads(raw).get("questions", [])
    except (ValueError, AttributeError):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="The AI returned an unreadable answer, try again")
    drafts: list[QuestionCreate] = []
    discarded = 0
    for item in items if isinstance(items, list) else []:
        try:
            draft = QuestionCreate.model_validate({**item, "skill_id": str(skill_id), "tags": [AI_TAG]})
        except (ValidationError, TypeError):
            discarded += 1
            continue
        if difficulty != "mixed":
            draft.difficulty = difficulty  # the instructor asked for one level; don't trust the model's label
        drafts.append(draft)
    return GenerateQuestionsResponse(drafts=drafts[:count], discarded=discarded + max(0, len(drafts) - count))


async def generate_drafts(
    skill_id: UUID, skill_name: str, description: str | None, count: int, difficulty: str, topic: str | None
) -> GenerateQuestionsResponse:
    if not settings.GROQ_API_KEY:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI question generation is not configured")
    raw = await _chat(SYSTEM_PROMPT, _user_prompt(skill_name, description, count, difficulty, topic))
    return parse_drafts(raw, skill_id, difficulty, count)
