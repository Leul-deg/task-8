import re
from datetime import datetime, timezone, date as date_type
from app.extensions import db
from app.models.listing import PropertyListing, ListingAmenity, ListingStatusHistory
from app.models.user import User
from app.utils.constants import ListingStatus, ListingAssetCategory
from app.services.audit_service import log_action

ALLOWED_TRANSITIONS = {
    'draft':          ['pending_review'],
    'pending_review': ['published', 'draft'],
    'published':      ['unpublished', 'expired', 'locked'],
    'unpublished':    ['draft', 'locked'],
    'expired':        ['locked'],
    'locked':         ['draft'],
}


def _parse_date(value):
    if isinstance(value, date_type):
        return value
    if isinstance(value, str):
        return datetime.strptime(value, '%Y-%m-%d').date()
    raise ValueError(f"Cannot parse date from {value!r}")


def _validate_listing_data(data: dict) -> dict:
    """Validate and normalise listing input. Returns cleaned data dict."""
    title = (data.get('title') or '').strip()
    if not (3 <= len(title) <= 200):
        raise ValueError("Title must be 3-200 characters")

    address_line1 = (data.get('address_line1') or '').strip()
    if not address_line1:
        raise ValueError("address_line1 is required")

    city = (data.get('city') or '').strip()
    if not city:
        raise ValueError("city is required")

    state = (data.get('state') or '').strip()
    if not state:
        raise ValueError("state is required")

    zip_code = (data.get('zip_code') or '').strip()
    if not re.match(r'^\d{5}(-\d{4})?$', zip_code):
        raise ValueError("Invalid zip code format")

    square_footage = data.get('square_footage')
    if square_footage is not None:
        square_footage = int(square_footage)
        if square_footage <= 0:
            raise ValueError("Square footage must be positive")

    monthly_rent_cents = data.get('monthly_rent_cents')
    if monthly_rent_cents is None or int(monthly_rent_cents) <= 0:
        raise ValueError("Monthly rent must be positive")
    monthly_rent_cents = int(monthly_rent_cents)

    deposit_cents = data.get('deposit_cents')
    if deposit_cents is None or int(deposit_cents) < 0:
        raise ValueError("Deposit cannot be negative")
    deposit_cents = int(deposit_cents)

    lease_start = _parse_date(data['lease_start'])
    lease_end = _parse_date(data['lease_end'])
    if lease_end <= lease_start:
        raise ValueError("Lease end date must be after start date")

    asset_category = (data.get('asset_category') or ListingAssetCategory.HOUSING.value).strip().lower()
    valid_categories = {c.value for c in ListingAssetCategory}
    if asset_category not in valid_categories:
        raise ValueError(f"asset_category must be one of: {sorted(valid_categories)}")

    return {
        **data,
        'title': title,
        'address_line1': address_line1,
        'city': city,
        'state': state,
        'zip_code': zip_code,
        'square_footage': square_footage,
        'monthly_rent_cents': monthly_rent_cents,
        'deposit_cents': deposit_cents,
        'lease_start': lease_start,
        'lease_end': lease_end,
        'asset_category': asset_category,
    }


def create_listing(data: dict, created_by: User) -> PropertyListing:
    data = _validate_listing_data(data)
    listing = PropertyListing(
        title=data['title'],
        address_line1=data['address_line1'],
        address_line2=data.get('address_line2'),
        city=data['city'],
        state=data['state'],
        zip_code=data['zip_code'],
        floor_plan_notes=data.get('floor_plan_notes'),
        square_footage=data.get('square_footage'),
        monthly_rent_cents=data['monthly_rent_cents'],
        deposit_cents=data['deposit_cents'],
        lease_start=data['lease_start'],
        lease_end=data['lease_end'],
        asset_category=data['asset_category'],
        status=ListingStatus.DRAFT.value,
        created_by_id=created_by.id,
        org_unit_id=data['org_unit_id'],
    )
    db.session.add(listing)
    db.session.flush()
    for amenity_name in data.get('amenities', []):
        db.session.add(ListingAmenity(listing_id=listing.id, name=amenity_name))
    _record_status_change(listing, None, ListingStatus.DRAFT.value, created_by, 'Created')
    db.session.commit()
    log_action(
        action='listing.create',
        resource_type='listing',
        resource_id=listing.id,
        user_id=created_by.id,
        new_value=listing.to_dict(),
    )
    return listing


def update_listing(listing: PropertyListing, data: dict, updated_by: User) -> PropertyListing:
    if listing.status in ('locked', 'expired'):
        raise ValueError(f'Cannot edit a listing with status "{listing.status}"')
    old = listing.to_dict()
    updatable = [
        'title', 'address_line1', 'address_line2', 'city', 'state', 'zip_code',
        'floor_plan_notes', 'square_footage', 'monthly_rent_cents', 'deposit_cents',
        'lease_start', 'lease_end', 'asset_category',
    ]
    for field in updatable:
        if field in data:
            setattr(listing, field, data[field])
    listing.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    log_action(
        action='listing.update',
        resource_type='listing',
        resource_id=listing.id,
        user_id=updated_by.id,
        old_value=old,
        new_value=listing.to_dict(),
    )
    return listing


def change_listing_status(
    listing: PropertyListing,
    new_status: str,
    changed_by: User,
    reason: str | None = None,
) -> PropertyListing:
    allowed = ALLOWED_TRANSITIONS.get(listing.status, [])
    if new_status not in allowed:
        raise ValueError(f"Cannot transition from '{listing.status}' to '{new_status}'")

    if new_status == ListingStatus.DRAFT.value and listing.status == ListingStatus.LOCKED.value:
        if not any(r.name == 'org_admin' for r in changed_by.roles):
            raise PermissionError("Only org admins can unlock listings")

    if new_status == ListingStatus.PUBLISHED.value:
        if not listing.title or not listing.address_line1 or not listing.monthly_rent_cents:
            raise ValueError("Listing must have title, address, and rent before publishing")

    if new_status == ListingStatus.UNPUBLISHED.value:
        if not reason:
            raise ValueError("A reason is required when unpublishing a listing")

    old_status = listing.status
    listing.status = new_status
    listing.updated_at = datetime.now(timezone.utc)
    if new_status == ListingStatus.PUBLISHED.value:
        listing.published_at = datetime.now(timezone.utc)
    elif new_status == ListingStatus.LOCKED.value:
        listing.locked_at = datetime.now(timezone.utc)
        listing.locked_by_id = changed_by.id

    _record_status_change(listing, old_status, new_status, changed_by, reason)
    db.session.commit()
    log_action(
        action='listing.status_change',
        resource_type='listing',
        resource_id=listing.id,
        user_id=changed_by.id,
        old_value={'status': old_status},
        new_value={'status': new_status, 'reason': reason},
    )
    return listing


def _record_status_change(
    listing: PropertyListing,
    old_status: str | None,
    new_status: str,
    changed_by: User | None,
    reason: str | None,
) -> None:
    # Skip history record for system actions with no user
    if changed_by is None:
        return
    history = ListingStatusHistory(
        listing_id=listing.id,
        old_status=old_status,
        new_status=new_status,
        changed_by_id=changed_by.id,
        reason=reason,
        changed_at=datetime.now(timezone.utc),
    )
    db.session.add(history)


def expire_stale_listings() -> int:
    """Auto-expire published listings whose lease_end date has passed."""
    from datetime import date
    today = date.today()
    stale = PropertyListing.query.filter(
        PropertyListing.status == ListingStatus.PUBLISHED.value,
        PropertyListing.lease_end < today,
    ).all()
    count = 0
    for listing in stale:
        listing.status = ListingStatus.EXPIRED.value
        listing.updated_at = datetime.now(timezone.utc)
        _record_status_change(
            listing,
            ListingStatus.PUBLISHED.value,
            ListingStatus.EXPIRED.value,
            None,
            'Auto-expired: lease end date passed',
        )
        log_action(
            action='listing.auto_expire',
            resource_type='listing',
            resource_id=listing.id,
        )
        count += 1
    if stale:
        db.session.commit()
    return count


def get_listing_detail(listing_id: int) -> dict:
    listing = PropertyListing.query.get_or_404(listing_id)
    data = listing.to_dict()
    data['amenities'] = [a.name for a in listing.amenities]
    data['status_history'] = [
        {
            'old_status': h.old_status,
            'new_status': h.new_status,
            'changed_by': h.changed_by_id,
            'reason': h.reason,
            'changed_at': h.changed_at.isoformat() if h.changed_at else None,
        }
        for h in ListingStatusHistory.query.filter_by(listing_id=listing_id)
            .order_by(ListingStatusHistory.changed_at.desc()).all()
    ]
    data['monthly_rent_display'] = f"${listing.monthly_rent_cents / 100:,.2f}"
    data['deposit_display'] = f"${listing.deposit_cents / 100:,.2f}"
    return data


def get_listings(
    org_unit_id=None,
    status=None,
    asset_category=None,
    min_rent=None,
    max_rent=None,
    search=None,
    page=1,
    per_page=20,
    allowed_org_ids: set | None = None,
) -> dict:
    query = PropertyListing.query
    if allowed_org_ids is not None:
        query = query.filter(PropertyListing.org_unit_id.in_(allowed_org_ids))
    if org_unit_id:
        query = query.filter_by(org_unit_id=org_unit_id)
    if status:
        query = query.filter_by(status=status)
    if asset_category:
        query = query.filter_by(asset_category=asset_category)
    if min_rent is not None:
        query = query.filter(PropertyListing.monthly_rent_cents >= min_rent)
    if max_rent is not None:
        query = query.filter(PropertyListing.monthly_rent_cents <= max_rent)
    if search:
        query = query.filter(
            PropertyListing.title.ilike(f'%{search}%') |
            PropertyListing.city.ilike(f'%{search}%')
        )
    total = query.count()
    listings = (
        query.order_by(PropertyListing.created_at.desc())
             .offset((page - 1) * per_page)
             .limit(per_page)
             .all()
    )
    return {
        'items': listings,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page,
    }
