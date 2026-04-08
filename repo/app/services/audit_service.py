import json
import uuid
from datetime import datetime, timezone
from flask import g
from app.extensions import db
from app.models.audit import AuditLog
from app.utils.masking import mask_field

SENSITIVE_KEYS = {
    'email', '_email', 'full_name', '_full_name',
    'address_line1', '_address_line1', 'address_line2', '_address_line2',
}


def _sanitize_audit_value(value):
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            if key in SENSITIVE_KEYS and item:
                sanitized[key] = mask_field(str(item), 'partial')
            else:
                sanitized[key] = _sanitize_audit_value(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_audit_value(item) for item in value]
    return value


def _sanitize_marshaled_json(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value
    return json.dumps(_sanitize_audit_value(parsed))


def serialize_audit_log(entry: AuditLog) -> dict:
    data = entry.to_dict()
    data['old_value'] = _sanitize_marshaled_json(data.get('old_value'))
    data['new_value'] = _sanitize_marshaled_json(data.get('new_value'))
    return data


def audit_log_in_scope(entry: AuditLog, allowed_org_ids: set[int]) -> bool:
    if not allowed_org_ids:
        return False

    resource_type = entry.resource_type
    resource_id = entry.resource_id
    if resource_id is None:
        return False

    from app.models.user import User
    from app.models.organization import OrgUnit
    from app.models.user import TempGrant
    from app.models.listing import PropertyListing
    from app.models.training import TrainingClass, ClassReview, CoachReply
    from app.models.moderation import ModerationReport, ModerationAppeal

    if resource_type == 'user':
        user = db.session.get(User, resource_id)
        return bool(user and any(m.org_unit_id in allowed_org_ids for m in user.org_memberships))
    if resource_type == 'temp_grant':
        grant = db.session.get(TempGrant, resource_id)
        return bool(grant and grant.user and any(m.org_unit_id in allowed_org_ids for m in grant.user.org_memberships))
    if resource_type == 'org_unit':
        org = db.session.get(OrgUnit, resource_id)
        return bool(org and org.id in allowed_org_ids)
    if resource_type == 'listing':
        listing = db.session.get(PropertyListing, resource_id)
        return bool(listing and listing.org_unit_id in allowed_org_ids)
    if resource_type == 'training_class':
        training_class = db.session.get(TrainingClass, resource_id)
        return bool(training_class and training_class.org_unit_id in allowed_org_ids)
    if resource_type in ('review', 'class_review'):
        review = db.session.get(ClassReview, resource_id)
        return bool(review and review.training_class.org_unit_id in allowed_org_ids)
    if resource_type == 'coach_reply':
        reply = db.session.get(CoachReply, resource_id)
        return bool(reply and reply.review.training_class.org_unit_id in allowed_org_ids)
    if resource_type == 'moderation_report':
        report = db.session.get(ModerationReport, resource_id)
        return bool(report and report.review.training_class.org_unit_id in allowed_org_ids)
    if resource_type == 'moderation_appeal':
        appeal = db.session.get(ModerationAppeal, resource_id)
        return bool(appeal and appeal.report.review.training_class.org_unit_id in allowed_org_ids)
    return False


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
        old_value=json.dumps(_sanitize_audit_value(old_value)) if old_value is not None else None,
        new_value=json.dumps(_sanitize_audit_value(new_value)) if new_value is not None else None,
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
