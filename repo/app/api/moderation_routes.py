from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from app.models.training import ClassReview
from app.models.moderation import ModerationReport, ModerationAppeal
from app.services.moderation_service import (
    report_review, hide_review, restore_review, finalize_report, file_appeal, resolve_appeal
)
from app.utils.decorators import require_permission
from app.utils.constants import ModerationStatus
from app.api.middleware import verify_hmac_signature

moderation_bp = Blueprint('moderation', __name__, url_prefix='/api/moderation')


def _is_htmx():
    return bool(request.headers.get('HX-Request'))


@moderation_bp.route('/reports', methods=['GET'])
@verify_hmac_signature
@login_required
@require_permission('review.moderate')
def list_reports():
    status_filter = request.args.get('status', ModerationStatus.PENDING.value)
    query = ModerationReport.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    reports = query.order_by(ModerationReport.created_at.desc()).all()
    if _is_htmx():
        return render_template('moderation/partials/report_list.html', reports=reports)
    return jsonify([r.to_dict() for r in reports]), 200


@moderation_bp.route('/reports', methods=['POST'])
@verify_hmac_signature
@login_required
def create_report():
    data = request.get_json(silent=True) or {}
    review_id = data.get('review_id')
    reason = data.get('reason', '').strip()
    if not review_id or not reason:
        return jsonify({'error': 'review_id and reason are required'}), 400
    review = ClassReview.query.get_or_404(review_id)
    report = report_review(review, current_user, reason, data.get('keyword_matches'))
    return jsonify(report.to_dict()), 201


@moderation_bp.route('/reports/<int:report_id>/hide', methods=['POST'])
@verify_hmac_signature
@login_required
@require_permission('review.moderate')
def hide(report_id: int):
    report = ModerationReport.query.get_or_404(report_id)
    reason = request.form.get('reason', '') if _is_htmx() else (request.get_json(silent=True) or {}).get('reason')
    report = hide_review(report, current_user, reason)
    if _is_htmx():
        return render_template('moderation/partials/report_card.html', report=report)
    return jsonify(report.to_dict()), 200


@moderation_bp.route('/reports/<int:report_id>/restore', methods=['POST'])
@verify_hmac_signature
@login_required
@require_permission('review.moderate')
def restore(report_id: int):
    report = ModerationReport.query.get_or_404(report_id)
    report = restore_review(report, current_user)
    if _is_htmx():
        return render_template('moderation/partials/report_card.html', report=report)
    return jsonify(report.to_dict()), 200


@moderation_bp.route('/reports/<int:report_id>/finalize', methods=['POST'])
@verify_hmac_signature
@login_required
@require_permission('review.moderate')
def finalize(report_id: int):
    report = ModerationReport.query.get_or_404(report_id)
    report = finalize_report(report, current_user)
    if _is_htmx():
        return render_template('moderation/partials/report_card.html', report=report)
    return jsonify(report.to_dict()), 200


@moderation_bp.route('/appeals', methods=['POST'])
@verify_hmac_signature
@login_required
def create_appeal():
    data = request.get_json(silent=True) or {}
    report_id = data.get('report_id')
    appeal_text = data.get('appeal_text', '').strip()
    if not report_id or not appeal_text:
        return jsonify({'error': 'report_id and appeal_text are required'}), 400
    report = ModerationReport.query.get_or_404(report_id)
    try:
        appeal = file_appeal(report, current_user, appeal_text)
    except PermissionError as e:
        return jsonify({'error': str(e)}), 403
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify(appeal.to_dict()), 201


@moderation_bp.route('/appeals/<int:appeal_id>/resolve', methods=['POST'])
@verify_hmac_signature
@login_required
@require_permission('review.moderate')
def resolve(appeal_id: int):
    appeal = ModerationAppeal.query.get_or_404(appeal_id)
    data = request.get_json(silent=True) or {}
    decision = data.get('decision')
    if not decision:
        return jsonify({'error': 'decision is required'}), 400
    try:
        appeal = resolve_appeal(appeal, current_user, decision, data.get('notes'))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify(appeal.to_dict()), 200
