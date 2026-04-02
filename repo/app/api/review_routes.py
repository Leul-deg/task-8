from flask import Blueprint, request, jsonify, current_app, abort
from flask_login import login_required, current_user
from app.models.training import TrainingClass, ClassReview, CoachReply
from app.services.review_service import (
    create_review, update_review, add_coach_reply, update_coach_reply, get_reviews_for_class
)
from app.services.permission_service import user_accessible_org_ids
from app.utils.decorators import require_permission
from app.api.middleware import verify_hmac_signature

review_bp = Blueprint('reviews', __name__, url_prefix='/api')


def _enforce_review_org_access(review):
    """Abort 403 if the current user cannot access the review's org."""
    tc = review.training_class
    if tc.org_unit_id not in user_accessible_org_ids(current_user):
        abort(403)


@review_bp.route('/classes/<int:class_id>/reviews', methods=['GET'])
@verify_hmac_signature
@login_required
def list_reviews(class_id: int):
    tc = TrainingClass.query.get_or_404(class_id)
    if tc.org_unit_id not in user_accessible_org_ids(current_user):
        abort(403)
    display_mode = (tc.org_unit.reviewer_display_mode
                    if tc.org_unit
                    else current_app.config.get('REVIEWER_DISPLAY_MODE', 'anonymous'))
    data = get_reviews_for_class(class_id, display_mode=display_mode)
    return jsonify(data['reviews']), 200


@review_bp.route('/classes/<int:class_id>/reviews', methods=['POST'])
@verify_hmac_signature
@login_required
@require_permission('review.create')
def create(class_id: int):
    tc = TrainingClass.query.get_or_404(class_id)
    if tc.org_unit_id not in user_accessible_org_ids(current_user):
        abort(403)
    data = request.get_json(silent=True) or {}
    try:
        review = create_review(class_id, current_user, data)
    except PermissionError as e:
        return jsonify({'error': str(e)}), 403
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify(review.to_dict()), 201


@review_bp.route('/reviews/<int:review_id>', methods=['GET'])
@verify_hmac_signature
@login_required
def get_review(review_id: int):
    review = ClassReview.query.get_or_404(review_id)
    _enforce_review_org_access(review)
    return jsonify(review.to_dict()), 200


@review_bp.route('/reviews/<int:review_id>', methods=['PUT'])
@verify_hmac_signature
@login_required
def update(review_id: int):
    review = ClassReview.query.get_or_404(review_id)
    _enforce_review_org_access(review)
    data = request.get_json(silent=True) or {}
    try:
        review = update_review(review, current_user, data)
    except (ValueError, PermissionError) as e:
        return jsonify({'error': str(e)}), 400
    return jsonify(review.to_dict()), 200


@review_bp.route('/reviews/<int:review_id>/reply', methods=['POST'])
@verify_hmac_signature
@login_required
@require_permission('review.reply')
def add_reply(review_id: int):
    review = ClassReview.query.get_or_404(review_id)
    _enforce_review_org_access(review)
    data = request.get_json(silent=True) or {}
    body = data.get('body', '').strip()
    if not body:
        return jsonify({'error': 'body is required'}), 400
    try:
        reply = add_coach_reply(review, current_user, body)
    except PermissionError as e:
        return jsonify({'error': str(e)}), 403
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify(reply.to_dict()), 201


@review_bp.route('/replies/<int:reply_id>', methods=['PUT'])
@verify_hmac_signature
@login_required
@require_permission('review.reply')
def update_reply(reply_id: int):
    reply = CoachReply.query.get_or_404(reply_id)
    _enforce_review_org_access(reply.review)
    data = request.get_json(silent=True) or {}
    body = data.get('body', '').strip()
    if not body:
        return jsonify({'error': 'body is required'}), 400
    try:
        reply = update_coach_reply(reply, current_user, body)
    except PermissionError as e:
        return jsonify({'error': str(e)}), 403
    return jsonify(reply.to_dict()), 200
