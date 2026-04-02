import re
from typing import Any


def validate_string(value: Any, field: str, min_len: int = 1, max_len: int = 255) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    value = value.strip()
    if len(value) < min_len:
        raise ValueError(f"{field} must be at least {min_len} characters")
    if len(value) > max_len:
        raise ValueError(f"{field} must be at most {max_len} characters")
    return value


def validate_email(email: str) -> str:
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    email = email.strip().lower()
    if not re.match(pattern, email):
        raise ValueError("Invalid email address")
    return email


def validate_integer(value: Any, field: str, min_val: int | None = None, max_val: int | None = None) -> int:
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be an integer")
    if min_val is not None and value < min_val:
        raise ValueError(f"{field} must be >= {min_val}")
    if max_val is not None and value > max_val:
        raise ValueError(f"{field} must be <= {max_val}")
    return value


def validate_rating(rating: Any) -> int:
    return validate_integer(rating, 'rating', min_val=1, max_val=5)


def validate_review_comment(comment: str | None) -> str | None:
    if comment is None:
        return None
    comment = comment.strip()
    if len(comment) == 0:
        return None
    if len(comment) < 20:
        raise ValueError("Comment must be at least 20 characters")
    if len(comment) > 1000:
        raise ValueError("Comment must be at most 1000 characters")
    return comment


def validate_review_tags(tags: list) -> list:
    from app.utils.constants import PREDEFINED_REVIEW_TAGS
    if not isinstance(tags, list):
        raise ValueError("Tags must be a list")
    if len(tags) > 5:
        raise ValueError("At most 5 tags are allowed")
    for tag in tags:
        if tag not in PREDEFINED_REVIEW_TAGS:
            raise ValueError(f"Invalid tag: {tag}")
    return tags


def validate_zip_code(zip_code: str) -> str:
    zip_code = zip_code.strip()
    if not re.match(r'^\d{5}(-\d{4})?$', zip_code):
        raise ValueError("Invalid ZIP code")
    return zip_code


def validate_ndc_code(ndc: str | None) -> str | None:
    if ndc is None:
        return None
    ndc = ndc.strip()
    if not re.match(r'^\d{4,5}-\d{3,4}-\d{1,2}$', ndc):
        raise ValueError("Invalid NDC code format")
    return ndc
