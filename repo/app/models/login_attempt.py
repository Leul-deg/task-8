from datetime import datetime, timezone
from app.extensions import db


class LoginAttempt(db.Model):
    """Records each login attempt for rate-limit enforcement.

    Keyed by IP address or username so both axes can be checked independently.
    Old rows are pruned on each login request; no background job is required.
    """
    __tablename__ = 'login_attempt'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(256), nullable=False, index=True)
    succeeded = db.Column(db.Boolean, nullable=False, default=False)
    attempted_at = db.Column(
        db.DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
