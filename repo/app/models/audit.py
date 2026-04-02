import uuid
from datetime import datetime, timezone
from sqlalchemy import event
from app.extensions import db


class AuditLog(db.Model):
    __tablename__ = 'audit_log'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    action = db.Column(db.String(128), nullable=False, index=True)
    resource_type = db.Column(db.String(64), nullable=False)
    resource_id = db.Column(db.Integer, nullable=True)
    old_value = db.Column(db.Text, nullable=True)
    new_value = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    request_id = db.Column(db.String(36), nullable=False, default=lambda: str(uuid.uuid4()))

    user = db.relationship('User', foreign_keys=[user_id])

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'user_id': self.user_id,
            'action': self.action,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'ip_address': self.ip_address,
            'request_id': self.request_id,
        }

    def __repr__(self) -> str:
        return f'<AuditLog {self.id}: {self.action} @ {self.timestamp}>'


@event.listens_for(AuditLog, 'before_update')
def prevent_audit_update(mapper, connection, target):
    raise RuntimeError("AuditLog records are immutable and cannot be updated")


@event.listens_for(AuditLog, 'before_delete')
def prevent_audit_delete(mapper, connection, target):
    raise RuntimeError("AuditLog records are immutable and cannot be deleted")
