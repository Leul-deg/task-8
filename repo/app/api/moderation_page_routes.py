from flask import Blueprint, render_template, request, redirect, flash
from flask_login import login_required, current_user
from app.models.moderation import ModerationReport, ModerationAppeal
from app.services.moderation_service import (
    report_review, hide_review, restore_review, finalize_report,
    file_appeal, resolve_appeal,
)
from app.utils.decorators import require_permission
from app.utils.constants import ModerationStatus

moderation_pages_bp = Blueprint('moderation_pages', __name__, url_prefix='/moderation')


@moderation_pages_bp.route('')
@login_required
@require_permission('review.moderate')
def queue():
    status_filter = request.args.get('status', ModerationStatus.PENDING.value)
    query = ModerationReport.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    reports = query.order_by(ModerationReport.created_at.desc()).all()
    if request.headers.get('HX-Request'):
        return render_template('moderation/partials/report_list.html', reports=reports)
    return render_template('moderation/queue.html', reports=reports, current_status=status_filter)


@moderation_pages_bp.route('/reports/<int:report_id>/hide', methods=['POST'])
@login_required
@require_permission('review.moderate')
def hide(report_id):
    report = ModerationReport.query.get_or_404(report_id)
    hide_review(report, current_user, request.form.get('reason', ''))
    flash('Review hidden', 'success')
    if request.headers.get('HX-Request'):
        return render_template('moderation/partials/report_card.html', report=report)
    return redirect('/moderation')


@moderation_pages_bp.route('/reports/<int:report_id>/restore', methods=['POST'])
@login_required
@require_permission('review.moderate')
def restore(report_id):
    report = ModerationReport.query.get_or_404(report_id)
    restore_review(report, current_user)
    flash('Review restored', 'success')
    if request.headers.get('HX-Request'):
        return render_template('moderation/partials/report_card.html', report=report)
    return redirect('/moderation')


@moderation_pages_bp.route('/reports/<int:report_id>/finalize', methods=['POST'])
@login_required
@require_permission('review.moderate')
def finalize(report_id):
    report = ModerationReport.query.get_or_404(report_id)
    finalize_report(report, current_user)
    flash('Report finalized', 'success')
    if request.headers.get('HX-Request'):
        return render_template('moderation/partials/report_card.html', report=report)
    return redirect('/moderation')


@moderation_pages_bp.route('/reports/<int:report_id>/appeal', methods=['POST'])
@login_required
def appeal(report_id):
    report = ModerationReport.query.get_or_404(report_id)
    try:
        file_appeal(report, current_user, request.form.get('appeal_text', ''))
        flash('Appeal filed successfully', 'success')
    except (ValueError, PermissionError) as e:
        flash(str(e), 'error')
    return redirect('/moderation')


@moderation_pages_bp.route('/appeals/<int:appeal_id>/resolve', methods=['POST'])
@login_required
@require_permission('review.moderate')
def resolve(appeal_id):
    appeal = ModerationAppeal.query.get_or_404(appeal_id)
    try:
        resolve_appeal(appeal, current_user, request.form.get('decision'), request.form.get('notes'))
        flash('Appeal resolved', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect('/moderation')
