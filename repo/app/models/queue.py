from datetime import datetime, timezone
from app.extensions import db
from app.utils.constants import JobStatus


class JobQueue(db.Model):
    __tablename__ = 'job_queue'

    id = db.Column(db.Integer, primary_key=True)
    job_type = db.Column(db.String(64), nullable=False, index=True)
    payload = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=JobStatus.PENDING.value, index=True)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    max_attempts = db.Column(db.Integer, nullable=False, default=3)
    next_retry_at = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'job_type': self.job_type,
            'payload': self.payload,
            'status': self.status,
            'attempts': self.attempts,
            'max_attempts': self.max_attempts,
            'next_retry_at': self.next_retry_at.isoformat() if self.next_retry_at else None,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }
