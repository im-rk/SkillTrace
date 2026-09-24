"""
Unit tests for item analysis (p-value + top/bottom-27% discrimination).
"""
import uuid

from app.modules.results.item_analysis import compute_item_analysis

STU = [uuid.uuid4() for _ in range(10)]


def test_p_value_is_the_plain_correctness_rate():
    stats = compute_item_analysis(
        total_scores={s: float(i) for i, s in enumerate(STU)},
        responses_by_question={uuid.uuid4(): {STU[0]: True, STU[1]: True, STU[2]: False, STU[3]: False}},
    )
    (only,) = stats.values()
    assert only.sample_size == 4
    assert only.p_value == 0.5


def test_perfectly_discriminating_question_scores_plus_one():
    """Every high scorer gets it right, every low scorer gets it wrong -- the
    textbook case, discrimination should be exactly +1.0."""
    scores = {s: float(9 - i) for i, s in enumerate(STU)}  # STU[0] highest ... STU[9] lowest
    qid = uuid.uuid4()
    responses = {s: (i < 5) for i, s in enumerate(STU)}  # top half correct, bottom half wrong
    stats = compute_item_analysis(scores, {qid: responses})
    assert stats[qid].discrimination == 1.0


def test_a_question_everyone_gets_right_has_zero_discrimination_and_p_value_one():
    scores = {s: float(i) for i, s in enumerate(STU)}
    qid = uuid.uuid4()
    stats = compute_item_analysis(scores, {qid: {s: True for s in STU}})
    assert stats[qid].p_value == 1.0
    assert stats[qid].discrimination == 0.0


def test_a_question_that_only_trips_up_the_best_students_can_score_negative():
    scores = {s: float(9 - i) for i, s in enumerate(STU)}
    qid = uuid.uuid4()
    responses = {s: not (i < 5) for i, s in enumerate(STU)}  # inverted: top half wrong, bottom half right
    stats = compute_item_analysis(scores, {qid: responses})
    assert stats[qid].discrimination == -1.0


def test_too_few_students_gives_no_discrimination_but_still_a_p_value():
    scores = {STU[0]: 5.0, STU[1]: 3.0}
    qid = uuid.uuid4()
    stats = compute_item_analysis(scores, {qid: {STU[0]: True, STU[1]: False}})
    assert stats[qid].p_value == 0.5
    assert stats[qid].discrimination is None


def test_a_question_nobody_has_answered_has_no_stats_but_is_not_an_error():
    stats = compute_item_analysis(total_scores={s: 1.0 for s in STU}, responses_by_question={uuid.uuid4(): {}})
    (only,) = stats.values()
    assert only.sample_size == 0
    assert only.p_value is None
    assert only.discrimination is None


def test_a_student_who_skipped_this_question_does_not_count_against_its_sample():
    """Discrimination is computed only from the students who actually answered THIS
    question, even though the top/bottom split is drawn from everyone's overall score."""
    scores = {s: float(9 - i) for i, s in enumerate(STU)}
    qid = uuid.uuid4()
    # top-group members STU[0], STU[1] both answer; bottom-group members STU[8], STU[9]
    # -- one of each skipped this particular question.
    responses = {STU[0]: True, STU[1]: True, STU[8]: False}
    stats = compute_item_analysis(scores, {qid: responses})
    assert stats[qid].sample_size == 3
    assert stats[qid].discrimination is None  # bottom group only has 1 respondent < MIN_GROUP_SIZE


def test_multiple_questions_are_scored_independently():
    scores = {s: float(9 - i) for i, s in enumerate(STU)}
    easy, hard = uuid.uuid4(), uuid.uuid4()
    stats = compute_item_analysis(
        scores,
        {
            easy: {s: True for s in STU},
            hard: {s: (i < 2) for i, s in enumerate(STU)},
        },
    )
    assert stats[easy].p_value == 1.0
    assert stats[hard].p_value == 0.2
