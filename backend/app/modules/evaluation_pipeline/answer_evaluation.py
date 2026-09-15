"""
Dispatches answer correctness checking by question_type. Takes the question's
content dict rather than the full ORM object, to stay decoupled from
question_bank's Question model; reuses quiz_engine's domain-level is_correct
for the text_input case -- the one genuinely general-purpose comparison
(whitespace/punctuation normalization, case sensitivity).
"""
from app.modules.question_bank.models import QuestionType
from app.modules.quiz_engine.domain.validation.answer_matching import is_correct


def evaluate_answer(question_type: QuestionType, content: dict, submitted_answer: str) -> bool:
    if question_type == QuestionType.multiple_choice:
        return submitted_answer == content["correct_choice_id"]
    if question_type == QuestionType.true_false:
        submitted_bool = (submitted_answer or "").strip().lower() in ("true", "1", "yes")
        return submitted_bool == content["correct_answer"]
    if question_type == QuestionType.text_input:
        return is_correct(submitted_answer, content["correct_answer"], case_sensitive=content.get("case_sensitive", False))
    raise ValueError(f"Unknown question_type: {question_type}")
