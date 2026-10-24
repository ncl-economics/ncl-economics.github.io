"""Signed, expiring tokens for the e-mailed review links."""
from __future__ import annotations

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

_SALT = "wp-portal-review"


def make_token(secret: str, submission_id: str) -> str:
    return URLSafeTimedSerializer(secret, salt=_SALT).dumps(submission_id)


def read_token(secret: str, token: str, max_age_seconds: int) -> str | None:
    try:
        return URLSafeTimedSerializer(secret, salt=_SALT).loads(token, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None
