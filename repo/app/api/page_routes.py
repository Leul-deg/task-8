from flask import Blueprint, render_template, redirect, request, flash, Response
from flask_login import login_required, current_user
from app.utils.decorators import require_role
from app.models.user import User, Role
from app.models.organization import OrgUnit
from app.extensions import db
from app.utils.constants import ReviewerDisplayMode
from app.services.permission_service import (
    get_permission_audit_report, export_permission_audit_csv, assign_role,
)

pages_bp = Blueprint('pages', __name__)


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
    query = User.query
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
    orgs = OrgUnit.query.order_by(OrgUnit.name).all()
    return render_template(
        'admin/org_settings.html',
        orgs=orgs,
        display_modes=[m.value for m in ReviewerDisplayMode],
    )


@pages_bp.route('/admin/org-settings/<int:org_id>', methods=['POST'])
@login_required
@require_role('org_admin')
def admin_update_org_settings(org_id: int):
    org = OrgUnit.query.get_or_404(org_id)
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
    start = request.args.get('start_date')
    end = request.args.get('end_date')
    entries = get_permission_audit_report(start_date=start, end_date=end)
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
