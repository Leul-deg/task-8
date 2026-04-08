import os
from flask import Blueprint, render_template, redirect, request, flash, Response, current_app
from flask_login import login_required, current_user
from app.utils.decorators import require_role
from app.models.user import User, Role
from app.models.organization import OrgUnit, UserOrgUnit
from app.extensions import db
from app.utils.constants import ReviewerDisplayMode
from app.services.permission_service import (
    get_permission_audit_report, export_permission_audit_csv, assign_role, user_accessible_org_ids,
)
from app.services.backup_service import create_backup, list_backups, prune_old_backups, restore_backup

pages_bp = Blueprint('pages', __name__)


def _accessible_org_ids():
    return user_accessible_org_ids(current_user)


def _user_in_scope(user: User) -> bool:
    allowed = _accessible_org_ids()
    if not allowed:
        return False
    memberships = {m.org_unit_id for m in user.org_memberships}
    return bool(memberships & allowed)


@pages_bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')


@pages_bp.route('/admin')
@login_required
@require_role('org_admin')
def admin_panel():
    return render_template('admin/index.html')


@pages_bp.route('/admin/users')
@login_required
@require_role('org_admin')
def admin_users():
    search = request.args.get('search', '').strip()
    allowed = _accessible_org_ids()
    query = User.query.join(UserOrgUnit).filter(UserOrgUnit.org_unit_id.in_(allowed)).distinct()
    if search:
        query = query.filter(User.username.ilike(f'%{search}%'))
    users = query.order_by(User.created_at.desc()).all()
    roles = Role.query.all()
    if request.headers.get('HX-Request'):
        return render_template('admin/partials/user_table.html', users=users, roles=roles)
    return render_template('admin/users.html', users=users, roles=roles)


@pages_bp.route('/admin/users/<int:user_id>/roles', methods=['POST'])
@login_required
@require_role('org_admin')
def admin_assign_role(user_id: int):
    user = User.query.get_or_404(user_id)
    if not _user_in_scope(user):
        return ('Forbidden', 403)
    role_name = request.form.get('role_name', '').strip()
    if role_name:
        role = Role.query.filter_by(name=role_name).first_or_404()
        try:
            assign_role(user, role, current_user.id)
        except ValueError as e:
            flash(str(e), 'error')
    roles = Role.query.all()
    if request.headers.get('HX-Request'):
        return render_template('admin/partials/user_table.html', users=[user], roles=roles)
    return redirect('/admin/users')


@pages_bp.route('/admin/org-settings')
@login_required
@require_role('org_admin')
def admin_org_settings():
    orgs = OrgUnit.query.filter(OrgUnit.id.in_(_accessible_org_ids())).order_by(OrgUnit.name).all()
    return render_template(
        'admin/org_settings.html',
        orgs=orgs,
        display_modes=[m.value for m in ReviewerDisplayMode],
    )


@pages_bp.route('/admin/backups')
@login_required
@require_role('org_admin')
def admin_backups():
    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    db_path = db_uri.replace('sqlite:///', '')
    backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
    backups = list_backups(backup_dir)
    return render_template('admin/backups.html', backups=backups)


@pages_bp.route('/admin/backups/run', methods=['POST'])
@login_required
@require_role('org_admin')
def admin_run_backup():
    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    db_path = db_uri.replace('sqlite:///', '')
    backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
    try:
        path = create_backup(db_path, backup_dir)
        prune_old_backups(backup_dir)
        flash(f'Backup created: {os.path.basename(path)}', 'success')
    except RuntimeError as e:
        flash(str(e), 'error')
    return redirect('/admin/backups')


@pages_bp.route('/admin/backups/restore', methods=['POST'])
@login_required
@require_role('org_admin')
def admin_restore_backup():
    filename = request.form.get('filename', '').strip()
    dry_run = request.form.get('dry_run') == '1'
    if not filename:
        flash('Backup filename is required.', 'error')
        return redirect('/admin/backups')
    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    db_path = db_uri.replace('sqlite:///', '')
    backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
    try:
        result = restore_backup(backup_dir, filename, db_path, dry_run=dry_run)
        if result.get('dry_run'):
            flash(f'Backup {filename} validated successfully.', 'success')
        else:
            flash(f'Backup {filename} restored successfully.', 'success')
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        flash(str(e), 'error')
    return redirect('/admin/backups')


@pages_bp.route('/admin/org-settings/<int:org_id>', methods=['POST'])
@login_required
@require_role('org_admin')
def admin_update_org_settings(org_id: int):
    org = OrgUnit.query.get_or_404(org_id)
    if org.id not in _accessible_org_ids():
        return ('Forbidden', 403)
    mode = request.form.get('reviewer_display_mode', '').strip()
    valid_modes = {m.value for m in ReviewerDisplayMode}
    if mode not in valid_modes:
        flash('Invalid display mode.', 'error')
    else:
        org.reviewer_display_mode = mode
        db.session.commit()
        flash(f'Display mode for "{org.name}" updated to "{mode}".', 'success')
    return redirect('/admin/org-settings')


@pages_bp.route('/admin/permissions/audit')
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
    return render_template('admin/permission_audit.html', entries=entries)
