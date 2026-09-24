"""
Item analysis: per-question difficulty (p-value) and discrimination, the classic
psychometric technique for judging whether a question is doing its job -- too
easy/hard, or (via discrimination) actually distinguishing students who know the
material from students who don't.

Pure function: no DB, no FastAPI -- takes plain data in, returns plain stats out,
same reasoning as the BKT domain functions (see ADR 0004).
"""
from dataclasses import dataclass
from statistics import mean
from uuid import UUID

# Kelley's classic top/bottom 27% split: the percentile shown (long ago) to maximize
# the separation between groups without wasting so many "middle" students that the
# comparison becomes noisy. A smaller class needs a floor on group size to mean
# anything at all -- below it, "top 27%" is one or two people and the comparison is noise.
DISCRIMINATION_PERCENTILE = 0.27
MIN_GROUP_SIZE = 2


@dataclass(frozen=True)
class ItemStats:
    question_id: UUID
    sample_size: int
    p_value: float | None  # fraction who answered correctly; None if nobody has answered yet
    discrimination: float | None  # top-group rate minus bottom-group rate; None if too few students to split


def _top_bottom_groups(total_scores: dict[UUID, float], percentile: float, min_group_size: int) -> tuple[set[UUID], set[UUID]]:
    students = sorted(total_scores, key=lambda s: total_scores[s], reverse=True)
    group_size = round(len(students) * percentile)
    if group_size < min_group_size or 2 * group_size > len(students):
        return set(), set()  # too few students overall for a meaningful split
    return set(students[:group_size]), set(students[-group_size:])


def compute_item_analysis(
    total_scores: dict[UUID, float],
    responses_by_question: dict[UUID, dict[UUID, bool]],
    percentile: float = DISCRIMINATION_PERCENTILE,
    min_group_size: int = MIN_GROUP_SIZE,
) -> dict[UUID, ItemStats]:
    top_group, bottom_group = _top_bottom_groups(total_scores, percentile, min_group_size)

    stats: dict[UUID, ItemStats] = {}
    for question_id, responses in responses_by_question.items():
        p_value = mean(responses.values()) if responses else None

        top = [correct for student_id, correct in responses.items() if student_id in top_group]
        bottom = [correct for student_id, correct in responses.items() if student_id in bottom_group]
        discrimination = mean(top) - mean(bottom) if len(top) >= min_group_size and len(bottom) >= min_group_size else None

        stats[question_id] = ItemStats(
            question_id=question_id, sample_size=len(responses), p_value=p_value, discrimination=discrimination
        )
    return stats
