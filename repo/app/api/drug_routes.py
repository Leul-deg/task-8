from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from app.models.drug import Drug
from app.services.drug_service import (
    create_drug, update_drug, submit_for_approval, approve_drug, reject_drug,
    search_drugs, import_drugs,
)
from app.services.permission_service import has_permission
from app.utils.decorators import require_permission
from app.api.middleware import verify_hmac_signature

drug_bp = Blueprint('drugs', __name__, url_prefix='/api/drugs')


def _can_view_unapproved(user) -> bool:
    return has_permission(user, 'drug.approve') or has_permission(user, 'drug.edit')


@drug_bp.route('', methods=['GET'])
@verify_hmac_signature
@login_required
def list_drugs():
    q = request.args.get('q', '')
    form_filter = request.args.get('form')
    status_filter = request.args.get('status')
    if status_filter and status_filter != 'approved' and not _can_view_unapproved(current_user):
        status_filter = None
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    result = search_drugs(q, form_filter=form_filter, status_filter=status_filter, page=page, per_page=per_page)
    if request.headers.get('HX-Request'):
        return render_template('drugs/partials/drug_results.html', **result, query=q)
    return jsonify([item['drug'].to_dict() for item in result['items']]), 200


@drug_bp.route('', methods=['POST'])
@verify_hmac_signature
@login_required
@require_permission('drug.create')
def create():
    data = request.get_json(silent=True) or {}
    try:
        drug = create_drug(data, current_user)
    except (ValueError, KeyError) as e:
        return jsonify({'error': str(e)}), 400
    return jsonify(drug.to_dict()), 201


@drug_bp.route('/<int:drug_id>', methods=['GET'])
@verify_hmac_signature
@login_required
def get_drug(drug_id: int):
    drug = Drug.query.get_or_404(drug_id)
    if drug.status != 'approved' and not _can_view_unapproved(current_user):
        return jsonify({'error': 'Forbidden'}), 403
    return jsonify(drug.to_dict()), 200


@drug_bp.route('/<int:drug_id>', methods=['PUT'])
@verify_hmac_signature
@login_required
@require_permission('drug.edit')
def update(drug_id: int):
    drug = Drug.query.get_or_404(drug_id)
    data = request.get_json(silent=True) or {}
    try:
        drug = update_drug(drug, data, current_user)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify(drug.to_dict()), 200


@drug_bp.route('/<int:drug_id>/submit', methods=['POST'])
@verify_hmac_signature
@login_required
def submit(drug_id: int):
    drug = Drug.query.get_or_404(drug_id)
    try:
        drug = submit_for_approval(drug, current_user)
    except PermissionError as e:
        return jsonify({'error': str(e)}), 403
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify(drug.to_dict()), 200


@drug_bp.route('/<int:drug_id>/approve', methods=['POST'])
@verify_hmac_signature
@login_required
@require_permission('drug.approve')
def approve(drug_id: int):
    drug = Drug.query.get_or_404(drug_id)
    try:
        drug = approve_drug(drug, current_user)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify(drug.to_dict()), 200


@drug_bp.route('/<int:drug_id>/reject', methods=['POST'])
@verify_hmac_signature
@login_required
@require_permission('drug.approve')
def reject(drug_id: int):
    drug = Drug.query.get_or_404(drug_id)
    data = request.get_json(silent=True) or {}
    reason = data.get('reason', '').strip()
    if not reason:
        return jsonify({'error': 'reason is required'}), 400
    try:
        drug = reject_drug(drug, current_user, reason)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify(drug.to_dict()), 200


@drug_bp.route('/import', methods=['POST'])
@verify_hmac_signature
@login_required
@require_permission('drug.import')
def bulk_import():
    import io
    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'file is required'}), 400
    file_bytes = io.BytesIO(file.read())
    result = import_drugs(file_bytes, current_user.id)
    return jsonify(result), 200
