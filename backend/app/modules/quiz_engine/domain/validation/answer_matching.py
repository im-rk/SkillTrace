"""
Domain validation for answer matching.
Provides normalization and correctness evaluation for text and choice answers.
"""

import re
import string


def normalize_answer(raw_answer: str, case_sensitive: bool = False) -> str:
    """
    Normalize answer string by:
      - Stripping leading and trailing whitespace.
      - Collapsing internal whitespace into single spaces.
      - Stripping trailing punctuation (e.g. '.', ',', ';', '!', '?').
      - Converting to lowercase (if not case_sensitive).

    Args:
        raw_answer: The raw answer string.
        case_sensitive: If True, retains original letter casing.

    Returns:
        Normalized string.
    """
    if raw_answer is None:
        return ""

    text = str(raw_answer).strip()
    # Collapse multiple whitespace characters into single space
    text = re.sub(r"\s+", " ", text)
    # Strip common trailing punctuation
    text = text.rstrip(string.punctuation)
    # Strip any whitespace exposed after punctuation strip
    text = text.strip()

    if not case_sensitive:
        text = text.lower()

    return text


def is_correct(
    submitted_answer: str,
    correct_answer: str,
    case_sensitive: bool = False,
) -> bool:
    """
    Evaluate if a submitted answer matches the expected correct answer.

    Args:
        submitted_answer: Answer provided by the student.
        correct_answer: Expected correct answer.
        case_sensitive: Whether letter case should be strictly enforced.

    Returns:
        True if matched, False otherwise.
    """
    norm_sub = normalize_answer(submitted_answer, case_sensitive=case_sensitive)
    norm_corr = normalize_answer(correct_answer, case_sensitive=case_sensitive)

    return norm_sub == norm_corr