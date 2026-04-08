from datetime import date as date_type
from flask import Blueprint, render_template, request, redirect, flash, abort, make_response
from flask_login import login_required, current_user
from app.extensions import db
from app.models.listing import PropertyListing
from app.models.organization import OrgUnit
from app.services.listing_service import (
    create_listing, update_listing, change_listing_status,
    get_listings, get_listing_detail,
)
from app.services.permission_service import has_permission, user_accessible_org_ids
from app.utils.decorators import require_permission
from app.utils.constants import ListingStatus, ListingAssetCategory

listing_pages_bp = Blueprint('listing_pages', __name__, url_prefix='/listings')


@listing_pages_bp.route('')
@login_required
def index():
    status = request.args.get('status')
    asset_category = request.args.get('asset_category')
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    allowed = user_accessible_org_ids(current_user)
    result = get_listings(status=status, asset_category=asset_category, search=search, page=page, per_page=per_page, allowed_org_ids=allowed)
    if request.headers.get('HX-Request'):
        return render_template('listings/partials/listing_grid.html', **result)
    resp = make_response(render_template(
        'listings/index.html',
        **result,
        search=search,
        statuses=ListingStatus,
        asset_categories=ListingAssetCategory,
        current_asset_category=asset_category,
        current_status=status,
    ))
    resp.headers['X-Offline-Cacheable'] = '1'
    return resp


@listing_pages_bp.route('/new')
@login_required
@require_permission('listing.create')
def new():
    orgs = OrgUnit.query.filter_by(is_active=True).all()
    return render_template('listings/form.html', listing=None, org_units=orgs)


@listing_pages_bp.route('', methods=['POST'])
@login_required
@require_permission('listing.create')
def create():
    raw_sqft = request.form.get('square_footage', '0').strip()
    target_org_id = int(request.form.get('org_unit_id'))
    if target_org_id not in user_accessible_org_ids(current_user):
        abort(403)
    if not has_permission(
        current_user,
        'listing.create',
        org_unit_id=target_org_id,
        asset_category=request.form.get('asset_category') or 'housing',
    ):
        abort(403)
    data = {
        'title': request.form.get('title'),
        'address_line1': request.form.get('address_line1'),
        'address_line2': request.form.get('address_line2'),
        'city': request.form.get('city'),
        'state': request.form.get('state'),
        'zip_code': request.form.get('zip_code'),
        'floor_plan_notes': request.form.get('floor_plan_notes'),
        'square_footage': int(raw_sqft) if raw_sqft else None,
        'monthly_rent_cents': int(float(request.form.get('monthly_rent', 0)) * 100),
        'deposit_cents': int(float(request.form.get('deposit', 0)) * 100),
        'lease_start': request.form.get('lease_start'),
        'lease_end': request.form.get('lease_end'),
        'asset_category': request.form.get('asset_category') or 'housing',
        'org_unit_id': target_org_id,
        'amenities': request.form.getlist('amenities'),
    }
    try:
        listing = create_listing(data, current_user)
        flash('Listing created successfully', 'success')
        return redirect(f'/listings/{listing.id}')
    except (ValueError, KeyError) as e:
        flash(str(e), 'error')
        orgs = OrgUnit.query.filter_by(is_active=True).all()
        return render_template('listings/form.html', listing=None, org_units=orgs, form_data=data), 400


@listing_pages_bp.route('/<int:listing_id>')
@login_required
def detail(listing_id):
    listing = PropertyListing.query.get_or_404(listing_id)
    if listing.org_unit_id not in user_accessible_org_ids(current_user):
        abort(403)
    data = get_listing_detail(listing_id)
    return render_template('listings/detail.html', listing=listing, detail=data)


@listing_pages_bp.route('/<int:listing_id>/edit')
@login_required
def edit(listing_id):
    listing = PropertyListing.query.get_or_404(listing_id)
    if not has_permission(
        current_user,
        'listing.edit',
        org_unit_id=listing.org_unit_id,
        asset_category=listing.asset_category,
        listing_status=listing.status,
    ):
        abort(403)
    if listing.status not in ('draft', 'unpublished'):
        flash('This listing cannot be edited in its current status', 'error')
        return redirect(f'/listings/{listing_id}')
    orgs = OrgUnit.query.filter_by(is_active=True).all()
    return render_template('listings/form.html', listing=listing, org_units=orgs)


@listing_pages_bp.route('/<int:listing_id>', methods=['POST'])
@login_required
def update(listing_id):
    listing = PropertyListing.query.get_or_404(listing_id)
    if not has_permission(
        current_user,
        'listing.edit',
        org_unit_id=listing.org_unit_id,
        asset_category=listing.asset_category,
        listing_status=listing.status,
    ):
        abort(403)
    if listing.status not in ('draft', 'unpublished'):
        flash('This listing cannot be edited in its current status', 'error')
        return redirect(f'/listings/{listing_id}')
    raw_sqft = request.form.get('square_footage', '0').strip()
    data = {
        'title': request.form.get('title'),
        'address_line1': request.form.get('address_line1'),
        'address_line2': request.form.get('address_line2'),
        'city': request.form.get('city'),
        'state': request.form.get('state'),
        'zip_code': request.form.get('zip_code'),
        'floor_plan_notes': request.form.get('floor_plan_notes'),
        'square_footage': int(raw_sqft) if raw_sqft else None,
        'monthly_rent_cents': int(float(request.form.get('monthly_rent', 0)) * 100),
        'deposit_cents': int(float(request.form.get('deposit', 0)) * 100),
        'lease_start': date_type.fromisoformat(request.form.get('lease_start')),
        'lease_end': date_type.fromisoformat(request.form.get('lease_end')),
        'asset_category': request.form.get('asset_category') or listing.asset_category,
        'org_unit_id': int(request.form.get('org_unit_id')),
        'amenities': request.form.getlist('amenities'),
    }
    try:
        update_listing(listing, data, current_user)
        flash('Listing updated successfully', 'success')
        return redirect(f'/listings/{listing_id}')
    except (ValueError, KeyError) as e:
        flash(str(e), 'error')
        orgs = OrgUnit.query.filter_by(is_active=True).all()
        return render_template('listings/form.html', listing=listing, org_units=orgs, form_data=data), 400


@listing_pages_bp.route('/<int:listing_id>/status', methods=['POST'])
@login_required
def change_status(listing_id):
    listing = PropertyListing.query.get_or_404(listing_id)
    if not has_permission(
        current_user,
        'listing.publish',
        org_unit_id=listing.org_unit_id,
        asset_category=listing.asset_category,
        listing_status=listing.status,
    ):
        abort(403)
    new_status = request.form.get('status')
    reason = request.form.get('reason')
    try:
        change_listing_status(listing, new_status, current_user, reason)
        flash(f'Status changed to {new_status}', 'success')
    except (ValueError, PermissionError) as e:
        flash(str(e), 'error')
    if request.headers.get('HX-Request'):
        updated = get_listing_detail(listing_id)
        listing = db.session.get(PropertyListing, listing_id)
        return render_template('listings/partials/status_section.html', listing=listing, detail=updated)
    return redirect(f'/listings/{listing_id}')


@listing_pages_bp.route('/<int:listing_id>/preview')
@login_required
def preview(listing_id):
    listing = PropertyListing.query.get_or_404(listing_id)
    if listing.org_unit_id not in user_accessible_org_ids(current_user):
        abort(403)
    data = get_listing_detail(listing_id)
    return render_template('listings/partials/preview_modal.html', listing=listing, detail=data)
