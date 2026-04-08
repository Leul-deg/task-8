from flask import Blueprint, request, jsonify, render_template, Response, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.models.user import User, Role, Permission, TempGrant
from app.models.organization import OrgUnit, UserOrgUnit
from app.utils.constants import ReviewerDisplayMode
from app.models.audit import AuditLog
from app.services.permission_service import (
    assign_role, remove_role, grant_temp_permission, revoke_temp_grant,
    get_permission_audit_report, export_permission_audit_csv, user_accessible_org_ids,
)
from app.services.audit_service import get_audit_logs, serialize_audit_log, audit_log_in_scope
from app.services.backup_service import create_backup, list_backups, prune_old_backups, restore_backup
from app.utils.decorators import require_permission, require_role
from app.api.middleware import verify_hmac_signature
import os

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


def _accessible_org_ids():
    return user_accessible_org_ids(current_user)


def _user_in_scope(user: User) -> bool:
    allowed = _accessible_org_ids()
    if not allowed:
        return False
    memberships = {m.org_unit_id for m in user.org_memberships}
    return bool(memberships & allowed)


def _org_in_scope(org: OrgUnit) -> bool:
    return org.id in _accessible_org_ids()


@admin_bp.route('/users', methods=['GET'])
@verify_hmac_signature
@login_required
@require_permission('admin.users')
def list_users():
    search = request.args.get('search', '').strip()
    allowed = _accessible_org_ids()
    if not allowed:
        return jsonify([]), 200
    query = User.query.join(UserOrgUnit).filter(UserOrgUnit.org_unit_id.in_(allowed)).distinct()
    if search:
        query = query.filter(User.username.ilike(f'%{search}%'))
    users = query.order_by(User.username).all()
    if request.headers.get('HX-Request'):
        roles = Role.query.all()
        return render_template('admin/partials/user_table.html', users=users, roles=roles)
    return jsonify([u.to_dict() for u in users]), 200


@admin_bp.route('/users/<int:user_id>', methods=['GET'])
@verify_hmac_signature
@login_required
@require_permission('admin.users')
def get_user(user_id: int):
    user = User.query.get_or_404(user_id)
    if not _user_in_scope(user):
        return jsonify({'error': 'Permission denied'}), 403
    return jsonify(user.to_dict()), 200


@admin_bp.route('/users/<int:user_id>/roles', methods=['POST'])
@verify_hmac_signature
@login_required
@require_permission('admin.roles')
def add_role(user_id: int):
    user = User.query.get_or_404(user_id)
    if not _user_in_scope(user):
        return jsonify({'error': 'Permission denied'}), 403
    if request.headers.get('HX-Request'):
        role_name = request.form.get('role_name', '').strip()
    else:
        data = request.get_json(silent=True) or {}
        role_name = data.get('role', '')
    role = Role.query.filter_by(name=role_name).first_or_404()
    assign_role(user, role, current_user.id)
    if request.headers.get('HX-Request'):
        roles = Role.query.all()
        return render_template('admin/partials/user_table.html', users=[user], roles=roles)
    return jsonify(user.to_dict()), 200


@admin_bp.route('/users/<int:user_id>/roles/<role_name>', methods=['DELETE'])
@verify_hmac_signature
@login_required
@require_permission('admin.roles')
def delete_role(user_id: int, role_name: str):
    user = User.query.get_or_404(user_id)
    if not _user_in_scope(user):
        return jsonify({'error': 'Permission denied'}), 403
    role = Role.query.filter_by(name=role_name).first_or_404()
    remove_role(user, role, current_user.id)
    return jsonify(user.to_dict()), 200


@admin_bp.route('/users/<int:user_id>/temp-grants', methods=['POST'])
@verify_hmac_signature
@login_required
@require_permission('permission.grant')
def create_temp_grant(user_id: int):
    user = User.query.get_or_404(user_id)
    if not _user_in_scope(user):
        return jsonify({'error': 'Permission denied'}), 403
    data = request.get_json(silent=True) or {}
    permission = Permission.query.filter_by(codename=data.get('permission')).first_or_404()
    hours = data.get('hours', current_app.config.get('TEMP_GRANT_DEFAULT_HOURS', 72))
    try:
        hours = int(hours)
    except (TypeError, ValueError):
        return jsonify({'error': 'hours must be a positive integer'}), 400
    if hours <= 0:
        return jsonify({'error': 'hours must be a positive integer'}), 400
    reason = data.get('reason', '').strip()
    if not reason:
        return jsonify({'error': 'reason is required'}), 400
    grant = grant_temp_permission(user, permission, current_user, reason, hours)
    return jsonify(grant.to_dict()), 201


@admin_bp.route('/temp-grants/<int:grant_id>/revoke', methods=['POST'])
@verify_hmac_signature
@login_required
@require_permission('permission.grant')
def revoke_grant(grant_id: int):
    grant = TempGrant.query.get_or_404(grant_id)
    if not _user_in_scope(grant.user):
        return jsonify({'error': 'Permission denied'}), 403
    revoke_temp_grant(grant, current_user)
    return jsonify(grant.to_dict()), 200


@admin_bp.route('/org-units', methods=['GET'])
@verify_hmac_signature
@login_required
@require_permission('admin.org_units')
def list_org_units():
    allowed = _accessible_org_ids()
    units = OrgUnit.query.filter(OrgUnit.id.in_(allowed)).order_by(OrgUnit.level, OrgUnit.name).all()
    return jsonify([u.to_dict() for u in units]), 200


@admin_bp.route('/org-units', methods=['POST'])
@verify_hmac_signature
@login_required
@require_permission('admin.org_units')
def create_org_unit():
    data = request.get_json(silent=True) or {}
    parent_id = data.get('parent_id')
    if parent_id is not None:
        parent = OrgUnit.query.get_or_404(parent_id)
        if not _org_in_scope(parent):
            return jsonify({'error': 'Permission denied'}), 403
    unit = OrgUnit(
        name=data['name'],
        code=data['code'],
        level=data['level'],
        parent_id=parent_id,
    )
    db.session.add(unit)
    db.session.commit()
    return jsonify(unit.to_dict()), 201


@admin_bp.route('/org-units/<int:org_id>/settings', methods=['GET'])
@verify_hmac_signature
@login_required
@require_permission('admin.org_units')
def get_org_settings(org_id: int):
    org = OrgUnit.query.get_or_404(org_id)
    if not _org_in_scope(org):
        return jsonify({'error': 'Permission denied'}), 403
    return jsonify({'reviewer_display_mode': org.reviewer_display_mode}), 200


@admin_bp.route('/org-units/<int:org_id>/settings', methods=['PATCH'])
@verify_hmac_signature
@login_required
@require_permission('admin.org_units')
def update_org_settings(org_id: int):
    org = OrgUnit.query.get_or_404(org_id)
    if not _org_in_scope(org):
        return jsonify({'error': 'Permission denied'}), 403
    data = request.get_json(silent=True) or {}
    mode = data.get('reviewer_display_mode')
    valid_modes = {m.value for m in ReviewerDisplayMode}
    if mode not in valid_modes:
        return jsonify({'error': f'reviewer_display_mode must be one of: {sorted(valid_modes)}'}), 400
    org.reviewer_display_mode = mode
    db.session.commit()
    return jsonify({'reviewer_display_mode': org.reviewer_display_mode}), 200


@admin_bp.route('/audit-logs', methods=['GET'])
@verify_hmac_signature
@login_required
@require_permission('admin.audit_log')
def audit_logs():
    allowed = _accessible_org_ids()
    logs = get_audit_logs(
        resource_type=request.args.get('resource_type'),
        resource_id=request.args.get('resource_id', type=int),
        user_id=request.args.get('user_id', type=int),
        action=request.args.get('action'),
        limit=request.args.get('limit', 100, type=int),
        offset=request.args.get('offset', 0, type=int),
    )
    logs = [log for log in logs if audit_log_in_scope(log, allowed)]
    return jsonify([serialize_audit_log(log) for log in logs]), 200


@admin_bp.route('/backup', methods=['POST'])
@verify_hmac_signature
@login_required
@require_permission('admin.backup')
def run_backup():
    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    db_path = db_uri.replace('sqlite:///', '')
    backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
    backup_path = create_backup(db_path, backup_dir)
    prune_old_backups(backup_dir)
    return jsonify({'backup_path': backup_path}), 200


@admin_bp.route('/backups', methods=['GET'])
@verify_hmac_signature
@login_required
@require_permission('admin.backup')
def list_backup_files():
    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    db_path = db_uri.replace('sqlite:///', '')
    backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
    return jsonify(list_backups(backup_dir)), 200


@admin_bp.route('/backups/restore', methods=['POST'])
@verify_hmac_signature
@login_required
@require_permission('admin.backup')
def restore_backup_file():
    data = request.get_json(silent=True) or {}
    filename = data.get('filename', '').strip()
    if not filename:
        return jsonify({'error': 'filename is required'}), 400
    dry_run = data.get('dry_run', False)
    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    db_path = db_uri.replace('sqlite:///', '')
    backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
    try:
        result = restore_backup(backup_dir, filename, db_path, dry_run=dry_run)
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 500
    return jsonify(result), 200


@admin_bp.route('/permissions/audit', methods=['GET'])
@verify_hmac_signature
@login_required
@require_role('org_admin')
def permission_audit():
    allowed = _accessible_org_ids()
    start = request.args.get('start_date')
    end = request.args.get('end_date')
    entries = get_permission_audit_report(start_date=start, end_date=end, allowed_org_ids=allowed)
    fmt = request.args.get('format')
    if fmt == 'csv':
        csv_data = export_permission_audit_csv(entries)
        return Response(
            csv_data,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=permission_audit.csv'},
        )
    if request.headers.get('HX-Request'):
        return render_template('admin/partials/audit_table.html', entries=entries)
    return jsonify([e.to_dict() if hasattr(e, 'to_dict') else e for e in entries]), 200
