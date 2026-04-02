import json
from datetime import datetime, timezone
from app.extensions import db


class TrainingClass(db.Model):
    __tablename__ = 'training_class'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    instructor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    org_unit_id = db.Column(db.Integer, db.ForeignKey('org_unit.id'), nullable=False)
    class_date = db.Column(db.Date, nullable=False)
    location = db.Column(db.String(255), nullable=False)
    max_attendees = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    instructor = db.relationship('User', foreign_keys=[instructor_id])
    org_unit = db.relationship('OrgUnit')
    attendees = db.relationship('ClassAttendee', back_populates='training_class', cascade='all, delete-orphan')
    reviews = db.relationship('ClassReview', back_populates='training_class', cascade='all, delete-orphan')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'instructor_id': self.instructor_id,
            'org_unit_id': self.org_unit_id,
            'class_date': self.class_date.isoformat() if self.class_date else None,
            'location': self.location,
            'max_attendees': self.max_attendees,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f'<TrainingClass {self.id}: {self.title}>'


class ClassAttendee(db.Model):
    __tablename__ = 'class_attendee'

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('training_class.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    registered_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    attended = db.Column(db.Boolean, nullable=False, default=False)

    training_class = db.relationship('TrainingClass', back_populates='attendees')
    user = db.relationship('User')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'class_id': self.class_id,
            'user_id': self.user_id,
            'registered_at': self.registered_at.isoformat() if self.registered_at else None,
            'attended': self.attended,
        }


class ClassReview(db.Model):
    __tablename__ = 'class_review'

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('training_class.id'), nullable=False, index=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    _tags = db.Column('tags', db.Text, nullable=True)
    comment = db.Column(db.Text, nullable=True)
    is_visible = db.Column(db.Boolean, nullable=False, default=True)
    is_moderated = db.Column(db.Boolean, nullable=False, default=False)
    moderation_reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    training_class = db.relationship('TrainingClass', back_populates='reviews')
    reviewer = db.relationship('User')
    coach_reply = db.relationship(
        'CoachReply', back_populates='review', uselist=False, cascade='all, delete-orphan'
    )
    moderation_reports = db.relationship(
        'ModerationReport', back_populates='review', cascade='all, delete-orphan'
    )

    @property
    def tags(self) -> list:
        if self._tags:
            return json.loads(self._tags)
        return []

    @tags.setter
    def tags(self, value: list) -> None:
        self._tags = json.dumps(value)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'class_id': self.class_id,
            'reviewer_id': self.reviewer_id,
            'rating': self.rating,
            'tags': self.tags,
            'comment': self.comment,
            'is_visible': self.is_visible,
            'is_moderated': self.is_moderated,
            'moderation_reason': self.moderation_reason,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class CoachReply(db.Model):
    __tablename__ = 'coach_reply'

    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey('class_review.id'), unique=True, nullable=False)
    instructor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    review = db.relationship('ClassReview', back_populates='coach_reply')
    instructor = db.relationship('User')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'review_id': self.review_id,
            'instructor_id': self.instructor_id,
            'body': self.body,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
