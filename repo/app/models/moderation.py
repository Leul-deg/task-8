import json
from datetime import datetime, timezone
from app.extensions import db
from app.utils.constants import ModerationStatus, AppealStatus


class ModerationReport(db.Model):
    __tablename__ = 'moderation_report'

    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey('class_review.id'), nullable=False, index=True)
    reported_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    reason = db.Column(db.Text, nullable=False)
    _keyword_matches = db.Column('keyword_matches', db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default=ModerationStatus.PENDING.value)
    resolved_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    review = db.relationship('ClassReview', back_populates='moderation_reports')
    reported_by = db.relationship('User', foreign_keys=[reported_by_id])
    resolved_by = db.relationship('User', foreign_keys=[resolved_by_id])
    appeals = db.relationship('ModerationAppeal', back_populates='report', cascade='all, delete-orphan')

    @property
    def keyword_matches(self) -> list | None:
        if self._keyword_matches:
            return json.loads(self._keyword_matches)
        return None

    @keyword_matches.setter
    def keyword_matches(self, value: list | None) -> None:
        self._keyword_matches = json.dumps(value) if value is not None else None

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'review_id': self.review_id,
            'reported_by_id': self.reported_by_id,
            'reason': self.reason,
            'keyword_matches': self.keyword_matches,
            'status': self.status,
            'resolved_by_id': self.resolved_by_id,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ModerationAppeal(db.Model):
    __tablename__ = 'moderation_appeal'

    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey('moderation_report.id'), nullable=False, index=True)
    appealed_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    appeal_text = db.Column(db.Text, nullable=False)
    filed_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    deadline = db.Column(db.DateTime, nullable=False)
    resolution_deadline = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=AppealStatus.PENDING.value)
    resolved_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolution_notes = db.Column(db.Text, nullable=True)

    report = db.relationship('ModerationReport', back_populates='appeals')
    appealed_by = db.relationship('User', foreign_keys=[appealed_by_id])
    resolved_by = db.relationship('User', foreign_keys=[resolved_by_id])

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'report_id': self.report_id,
            'appealed_by_id': self.appealed_by_id,
            'appeal_text': self.appeal_text,
            'filed_at': self.filed_at.isoformat() if self.filed_at else None,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'resolution_deadline': self.resolution_deadline.isoformat() if self.resolution_deadline else None,
            'status': self.status,
            'resolved_by_id': self.resolved_by_id,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolution_notes': self.resolution_notes,
        }
