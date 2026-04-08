import csv
import io
from datetime import datetime, timezone, timedelta
from app.extensions import db
from app.models.user import User, Permission, TempGrant, Role
from app.services.audit_service import log_action, audit_log_in_scope

LISTING_PERMISSION_SCOPE = {
    'listing.create': {
        'asset_categories': {'housing', 'office'},
        'statuses': None,
    },
    'listing.edit': {
        'asset_categories': {'housing', 'office'},
        'statuses': {'draft', 'unpublished'},
    },
    'listing.publish': {
        'asset_categories': {'housing', 'office'},
        'statuses': {'draft', 'pending_review', 'published', 'unpublished', 'expired', 'locked'},
    },
}


def _scope_matches(codename: str, asset_category: str | None, listing_status: str | None) -> bool:
    rule = LISTING_PERMISSION_SCOPE.get(codename)
    if not rule:
        return True
    allowed_categories = rule.get('asset_categories')
    allowed_statuses = rule.get('statuses')
    if asset_category is not None and allowed_categories is not None and asset_category not in allowed_categories:
        return False
    if listing_status is not None and allowed_statuses is not None and listing_status not in allowed_statuses:
        return False
    return True


def has_permission(
    user: User,
    codename: str,
    org_unit_id: int | None = None,
    asset_category: str | None = None,
    listing_status: str | None = None,
) -> bool:
    """Check if a user has a permission via roles or active temp grants.

    If org_unit_id is provided, also verify the user has access to that org unit
    (direct membership or via an ancestor unit).
    """
    permission_granted = False

    for role in user.roles:
        if role.permissions.filter_by(codename=codename).first() and _scope_matches(codename, asset_category, listing_status):
            permission_granted = True
            break

    if not permission_granted:
        now = datetime.now(timezone.utc)
        grant = TempGrant.query.filter_by(
            user_id=user.id, is_active=True
        ).join(Permission).filter(Permission.codename == codename).first()
        if grant:
            expires_at = grant.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at > now and _scope_matches(codename, asset_category, listing_status):
                permission_granted = True

    if not permission_granted:
        return False

    if org_unit_id is None:
        return True

    # Verify org unit access
    from app.models.organization import OrgUnit, UserOrgUnit
    user_org_ids = {uo.org_unit_id for uo in UserOrgUnit.query.filter_by(user_id=user.id).all()}

    if org_unit_id in user_org_ids:
        return True

    # Walk up the ancestor chain
    current = db.session.get(OrgUnit, org_unit_id)
    while current and current.parent_id:
        if current.parent_id in user_org_ids:
            return True
        current = db.session.get(OrgUnit, current.parent_id)

    return False


def user_accessible_org_ids(user: User) -> set[int]:
    """Return all org unit IDs the user may read from.

    Includes every org unit the user is directly assigned to, plus all of
    their descendants — a campus-level member can read listings that belong
    to any department under their campus.
    """
    from app.models.organization import UserOrgUnit
    ids: set[int] = set()
    for membership in UserOrgUnit.query.filter_by(user_id=user.id).all():
        ids.add(membership.org_unit_id)
        for desc in membership.org_unit.get_descendants():
            ids.add(desc.id)
    return ids


def assign_role(user: User, role: Role, admin_id: int) -> None:
    if role in user.roles:
        return
    user.roles.append(role)
    db.session.commit()
    log_action(
        action='permission.role_assign',
        resource_type='user',
        resource_id=user.id,
        user_id=admin_id,
        new_value={'role': role.name},
    )


def remove_role(user: User, role: Role, admin_id: int) -> None:
    if role.name == 'org_admin':
        admin_count = (
            db.session.query(User)
            .join(User.roles)
            .filter(Role.name == 'org_admin', User.is_active == True)
            .count()
        )
        if admin_count <= 1:
            raise ValueError("Cannot remove the last org_admin role")

    if role not in user.roles:
        return
    user.roles.remove(role)
    db.session.commit()
    log_action(
        action='permission.role_remove',
        resource_type='user',
        resource_id=user.id,
        user_id=admin_id,
        old_value={'role': role.name},
    )


def grant_temp_permission(
    user: User,
    permission: Permission,
    granted_by: User,
    reason: str,
    hours: int,
) -> TempGrant:
    now = datetime.now(timezone.utc)
    grant = TempGrant(
        user_id=user.id,
        permission_id=permission.id,
        granted_by_id=granted_by.id,
        reason=reason,
        granted_at=now,
        expires_at=now + timedelta(hours=hours),
        is_active=True,
    )
    db.session.add(grant)
    db.session.commit()
    log_action(
        action='permission.grant',
        resource_type='temp_grant',
        resource_id=grant.id,
        user_id=granted_by.id,
        new_value={'permission': permission.codename, 'hours': hours, 'reason': reason},
    )
    return grant


def revoke_temp_grant(grant: TempGrant, revoked_by: User) -> None:
    grant.is_active = False
    grant.revoked_at = datetime.now(timezone.utc)
    grant.revoked_by_id = revoked_by.id
    db.session.commit()
    log_action(
        action='permission.revoke',
        resource_type='temp_grant',
        resource_id=grant.id,
        user_id=revoked_by.id,
    )


def expire_temp_grants() -> int:
    """Deactivate all expired temp grants. Returns count of deactivated grants."""
    now = datetime.now(timezone.utc)
    expired = TempGrant.query.filter(
        TempGrant.is_active == True,
        TempGrant.expires_at <= now,
    ).all()
    for grant in expired:
        grant.is_active = False
    if expired:
        db.session.commit()
    return len(expired)


def get_permission_audit_report(
    org_unit_id=None,
    start_date=None,
    end_date=None,
    allowed_org_ids: set[int] | None = None,
) -> list[dict]:
    """Return permission-related audit log entries."""
    from app.models.audit import AuditLog
    query = AuditLog.query.filter(AuditLog.action.like('permission.%'))
    if start_date:
        query = query.filter(AuditLog.timestamp >= start_date)
    if end_date:
        query = query.filter(AuditLog.timestamp <= end_date)
    entries = query.order_by(AuditLog.timestamp.desc()).all()
    if allowed_org_ids is not None:
        entries = [e for e in entries if audit_log_in_scope(e, allowed_org_ids)]
    return [e.to_dict() for e in entries]


def export_permission_audit_csv(entries: list[dict]) -> str:
    """Convert audit entries to CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Timestamp', 'User ID', 'Action', 'Resource Type', 'Resource ID', 'Details'])
    for e in entries:
        writer.writerow([
            e.get('timestamp'),
            e.get('user_id'),
            e.get('action'),
            e.get('resource_type'),
            e.get('resource_id'),
            str(e.get('new_value', e.get('old_value', ''))),
        ])
    return output.getvalue()
