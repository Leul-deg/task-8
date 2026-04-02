import json
import uuid
from datetime import datetime, timezone
from flask import g
from app.extensions import db
from app.models.audit import AuditLog


def log_action(
    action: str,
    resource_type: str,
    resource_id: int | None = None,
    user_id: int | None = None,
    old_value: dict | None = None,
    new_value: dict | None = None,
    ip_address: str | None = None,
    request_id: str | None = None,
) -> AuditLog:
    if not request_id:
        request_id = getattr(g, 'request_id', None)
    if not ip_address:
        ip_address = getattr(g, 'ip_address', None)
    entry = AuditLog(
        timestamp=datetime.now(timezone.utc),
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        old_value=json.dumps(old_value) if old_value is not None else None,
        new_value=json.dumps(new_value) if new_value is not None else None,
        ip_address=ip_address,
        request_id=request_id or str(uuid.uuid4()),
    )
    db.session.add(entry)
    db.session.commit()
    return entry


def get_audit_logs(
    resource_type: str | None = None,
    resource_id: int | None = None,
    user_id: int | None = None,
    action: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLog]:
    query = AuditLog.query
    if resource_type:
        query = query.filter_by(resource_type=resource_type)
    if resource_id is not None:
        query = query.filter_by(resource_id=resource_id)
    if user_id is not None:
        query = query.filter_by(user_id=user_id)
    if action:
        query = query.filter(AuditLog.action.like(f'{action}%'))
    return query.order_by(AuditLog.timestamp.desc()).limit(limit).offset(offset).all()
