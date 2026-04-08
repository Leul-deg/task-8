import pytest
from datetime import date


def _listing_payload(org_unit_id):
    return {
        'title': 'Studio Apt',
        'address_line1': '10 Elm St',
        'city': 'Chicago',
        'state': 'IL',
        'zip_code': '60601',
        'monthly_rent_cents': 90000,
        'deposit_cents': 90000,
        'lease_start': '2026-07-01',
        'lease_end': '2027-06-30',
        'org_unit_id': org_unit_id,
    }


@pytest.fixture
def org_unit_id(db):
    from app.models.organization import OrgUnit
    org = OrgUnit.query.filter_by(code='TC1').first()
    return org.id


class TestListingAPI:
    def test_create_requires_auth(self, client, org_unit_id):
        resp = client.post('/api/listings', json=_listing_payload(org_unit_id))
        assert resp.status_code == 401

    def test_create_listing(self, client, org_unit_id):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.post('/api/listings', json=_listing_payload(org_unit_id))
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['title'] == 'Studio Apt'
        assert data['status'] == 'draft'

    def test_list_listings(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.get('/api/listings')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_get_listing(self, client, org_unit_id):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        create_resp = client.post('/api/listings', json=_listing_payload(org_unit_id))
        listing_id = create_resp.get_json()['id']
        resp = client.get(f'/api/listings/{listing_id}')
        assert resp.status_code == 200

    def test_staff_receives_masked_address_in_json(self, client, org_unit_id):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        create_resp = client.post('/api/listings', json=_listing_payload(org_unit_id))
        listing_id = create_resp.get_json()['id']
        client.post('/auth/logout')
        client.post('/auth/login', json={'username': 'staffuser', 'password': 'staffpass'})
        resp = client.get(f'/api/listings/{listing_id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['address_line1'] != '10 Elm St'
        assert data['address_line1'].startswith('10')

    def test_admin_receives_full_address_in_json(self, client, org_unit_id):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        create_resp = client.post('/api/listings', json=_listing_payload(org_unit_id))
        listing_id = create_resp.get_json()['id']
        resp = client.get(f'/api/listings/{listing_id}')
        assert resp.status_code == 200
        assert resp.get_json()['address_line1'] == '10 Elm St'

    def test_update_listing(self, client, org_unit_id):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        create_resp = client.post('/api/listings', json=_listing_payload(org_unit_id))
        listing_id = create_resp.get_json()['id']
        resp = client.put(f'/api/listings/{listing_id}', json={'title': 'Updated Apt'})
        assert resp.status_code == 200
        assert resp.get_json()['title'] == 'Updated Apt'

    def test_update_listing_status(self, client, org_unit_id):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        create_resp = client.post('/api/listings', json=_listing_payload(org_unit_id))
        listing_id = create_resp.get_json()['id']
        # Must go through pending_review before published
        client.post(f'/api/listings/{listing_id}/status', json={'status': 'pending_review'})
        resp = client.post(f'/api/listings/{listing_id}/status', json={'status': 'published'})
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'published'

    def test_invalid_status_transition(self, client, org_unit_id):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        create_resp = client.post('/api/listings', json=_listing_payload(org_unit_id))
        listing_id = create_resp.get_json()['id']
        # draft → published directly is not allowed
        resp = client.post(f'/api/listings/{listing_id}/status', json={'status': 'published'})
        assert resp.status_code == 400

    def test_get_nonexistent_listing(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.get('/api/listings/99999')
        assert resp.status_code == 404

    def test_page_edit_form_submission(self, client, org_unit_id):
        """POST to /listings/<id> from the edit form persists changes and redirects."""
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        create_resp = client.post('/api/listings', json=_listing_payload(org_unit_id))
        assert create_resp.status_code == 201
        listing_id = create_resp.get_json()['id']

        form_data = {
            'title': 'Updated Studio Apt',
            'address_line1': '20 Oak Ave',
            'address_line2': '',
            'city': 'Chicago',
            'state': 'IL',
            'zip_code': '60601',
            'monthly_rent': '950.00',
            'deposit': '950.00',
            'lease_start': '2026-07-01',
            'lease_end': '2027-06-30',
            'square_footage': '600',
            'floor_plan_notes': '',
            'org_unit_id': str(org_unit_id),
            'amenities': ['parking', 'wifi'],
        }
        resp = client.post(f'/listings/{listing_id}', data=form_data,
                           follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers['Location'].endswith(f'/listings/{listing_id}')

        detail_resp = client.get(f'/api/listings/{listing_id}')
        assert detail_resp.status_code == 200
        assert detail_resp.get_json()['title'] == 'Updated Studio Apt'
