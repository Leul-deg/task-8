from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from app.models.listing import PropertyListing
from app.services.listing_service import (
    create_listing, update_listing, change_listing_status, get_listings, get_listing_detail,
)
from app.services.permission_service import has_permission, user_accessible_org_ids
from app.utils.masking import get_mask_type_for_role, mask_field
from app.utils.decorators import require_permission
from app.api.middleware import verify_hmac_signature

listing_bp = Blueprint('listings', __name__, url_prefix='/api/listings')


def _is_htmx():
    return bool(request.headers.get('HX-Request'))


def _serialize_listing_for_user(listing: PropertyListing):
    data = listing.to_dict()
    mask_type = get_mask_type_for_role(current_user.roles, 'address')
    if mask_type != 'none':
        data['address_line1'] = mask_field(data.get('address_line1') or '', mask_type)
        data['address_line2'] = mask_field(data.get('address_line2') or '', mask_type) if data.get('address_line2') else None
    return data


@listing_bp.route('', methods=['GET'])
@verify_hmac_signature
@login_required
def list_listings():
    org_unit_id = request.args.get('org_unit_id', type=int)
    status = request.args.get('status')
    asset_category = request.args.get('asset_category')
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    allowed = user_accessible_org_ids(current_user)
    if org_unit_id and org_unit_id not in allowed:
        return jsonify({'error': 'Permission denied'}), 403
    result = get_listings(org_unit_id=org_unit_id, status=status, asset_category=asset_category, search=search,
                          page=page, per_page=per_page, allowed_org_ids=allowed)
    if _is_htmx():
        return render_template('listings/partials/listing_grid.html', **result)
    return jsonify([_serialize_listing_for_user(l) for l in result['items']]), 200


@listing_bp.route('', methods=['POST'])
@verify_hmac_signature
@login_required
@require_permission('listing.create')
def create():
    data = request.get_json(silent=True) or {}
    target_org_id = data.get('org_unit_id')
    if target_org_id not in user_accessible_org_ids(current_user):
        return jsonify({'error': 'Permission denied'}), 403
    if not has_permission(
        current_user,
        'listing.create',
        org_unit_id=target_org_id,
        asset_category=data.get('asset_category'),
    ):
        return jsonify({'error': 'Permission denied'}), 403
    try:
        listing = create_listing(data, current_user)
    except (ValueError, KeyError) as e:
        return jsonify({'error': str(e)}), 400
    return jsonify(_serialize_listing_for_user(listing)), 201


@listing_bp.route('/<int:listing_id>', methods=['GET'])
@verify_hmac_signature
@login_required
def get_listing(listing_id: int):
    listing = PropertyListing.query.get_or_404(listing_id)
    if listing.org_unit_id not in user_accessible_org_ids(current_user):
        return jsonify({'error': 'Permission denied'}), 403
    return jsonify(_serialize_listing_for_user(listing)), 200


@listing_bp.route('/<int:listing_id>', methods=['PUT'])
@verify_hmac_signature
@login_required
def update(listing_id: int):
    listing = PropertyListing.query.get_or_404(listing_id)
    if not has_permission(
        current_user,
        'listing.edit',
        org_unit_id=listing.org_unit_id,
        asset_category=listing.asset_category,
        listing_status=listing.status,
    ):
        return jsonify({'error': 'Permission denied'}), 403
    data = request.get_json(silent=True) or {}
    try:
        listing = update_listing(listing, data, current_user)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify(_serialize_listing_for_user(listing)), 200


@listing_bp.route('/<int:listing_id>/status', methods=['POST'])
@verify_hmac_signature
@login_required
def update_status(listing_id: int):
    listing = PropertyListing.query.get_or_404(listing_id)
    if not has_permission(
        current_user,
        'listing.publish',
        org_unit_id=listing.org_unit_id,
        asset_category=listing.asset_category,
        listing_status=listing.status,
    ):
        return jsonify({'error': 'Permission denied'}), 403
    if _is_htmx():
        new_status = request.form.get('status')
        reason = request.form.get('reason')
    else:
        data = request.get_json(silent=True) or {}
        new_status = data.get('status')
        reason = data.get('reason')
    if not new_status:
        return jsonify({'error': 'status is required'}), 400
    try:
        listing = change_listing_status(listing, new_status, current_user, reason)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    if _is_htmx():
        from app.extensions import db
        updated = get_listing_detail(listing_id)
        listing = db.session.get(PropertyListing, listing_id)
        return render_template('listings/partials/status_section.html', listing=listing, detail=updated)
    return jsonify(_serialize_listing_for_user(listing)), 200


@listing_bp.route('/<int:listing_id>/preview', methods=['GET'])
@verify_hmac_signature
@login_required
def preview(listing_id: int):
    listing = PropertyListing.query.get_or_404(listing_id)
    if listing.org_unit_id not in user_accessible_org_ids(current_user):
        return jsonify({'error': 'Permission denied'}), 403
    detail = get_listing_detail(listing_id)
    return render_template('listings/partials/preview_modal.html', listing=listing, detail=detail)
