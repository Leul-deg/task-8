import pytest


def _drug_payload(**overrides):
    base = {
        'generic_name': 'Lisinopril',
        'strength': '10mg',
        'form': 'tablet',
        'description': 'ACE inhibitor for hypertension',
    }
    base.update(overrides)
    return base


class TestDrugAPI:
    def test_create_drug_requires_auth(self, client):
        resp = client.post('/api/drugs', json=_drug_payload())
        assert resp.status_code == 401

    def test_create_drug(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.post('/api/drugs', json=_drug_payload())
        assert resp.status_code == 201
        assert resp.get_json()['generic_name'] == 'Lisinopril'
        assert resp.get_json()['status'] == 'draft'

    def test_list_drugs(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.get('/api/drugs')
        assert resp.status_code == 200

    def test_approve_workflow(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        drug_id = client.post('/api/drugs', json=_drug_payload()).get_json()['id']
        submit_resp = client.post(f'/api/drugs/{drug_id}/submit')
        assert submit_resp.status_code == 200
        approve_resp = client.post(f'/api/drugs/{drug_id}/approve')
        assert approve_resp.status_code == 200
        assert approve_resp.get_json()['status'] == 'approved'

    def test_reject_drug(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        drug_id = client.post('/api/drugs', json=_drug_payload()).get_json()['id']
        client.post(f'/api/drugs/{drug_id}/submit')
        resp = client.post(f'/api/drugs/{drug_id}/reject', json={'reason': 'Missing info'})
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'rejected'

    def test_get_drug(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        drug_id = client.post('/api/drugs', json=_drug_payload()).get_json()['id']
        resp = client.get(f'/api/drugs/{drug_id}')
        assert resp.status_code == 200

    def test_bulk_import(self, client):
        import io
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        csv_content = (
            b"generic_name,strength,form,description\n"
            b"Aspirin,100mg,tablet,Pain reliever\n"
            b"Ibuprofen,200mg,tablet,Anti-inflammatory\n"
        )
        resp = client.post(
            '/api/drugs/import',
            data={'file': (io.BytesIO(csv_content), 'drugs.csv')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['imported'] == 2
        assert data['skipped'] == 0


class TestDrugApprovalVisibility:
    """Non-privileged users must only see approved drugs."""

    def _create_draft_drug(self, client, name='TestDrug'):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.post('/api/drugs', json=_drug_payload(generic_name=name))
        assert resp.status_code == 201
        drug_id = resp.get_json()['id']
        client.post('/auth/logout')
        return drug_id

    def _create_approved_drug(self, client, name='ApprovedDrug'):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.post('/api/drugs', json=_drug_payload(generic_name=name))
        drug_id = resp.get_json()['id']
        client.post(f'/api/drugs/{drug_id}/submit')
        client.post(f'/api/drugs/{drug_id}/approve')
        client.post('/auth/logout')
        return drug_id

    def test_staff_cannot_list_draft_drugs(self, client):
        """Staff ?status=draft filter is silently ignored — only approved returned."""
        self._create_draft_drug(client, 'DraftOnly')
        client.post('/auth/login', json={'username': 'staffuser', 'password': 'staffpass'})
        resp = client.get('/api/drugs?status=draft')
        assert resp.status_code == 200
        drugs = resp.get_json()
        assert all(d['status'] == 'approved' for d in drugs)

    def test_staff_cannot_view_draft_drug_by_id(self, client):
        drug_id = self._create_draft_drug(client, 'HiddenDraft')
        client.post('/auth/login', json={'username': 'staffuser', 'password': 'staffpass'})
        resp = client.get(f'/api/drugs/{drug_id}')
        assert resp.status_code == 403

    def test_admin_can_list_draft_drugs(self, client):
        self._create_draft_drug(client, 'AdminDraft')
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.get('/api/drugs?status=draft')
        assert resp.status_code == 200
        drugs = resp.get_json()
        assert any(d['status'] == 'draft' for d in drugs)

    def test_admin_can_view_draft_drug_by_id(self, client):
        drug_id = self._create_draft_drug(client, 'AdminViewDraft')
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.get(f'/api/drugs/{drug_id}')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'draft'

    def test_staff_can_see_approved_drugs(self, client):
        self._create_approved_drug(client, 'VisibleApproved')
        client.post('/auth/login', json={'username': 'staffuser', 'password': 'staffpass'})
        resp = client.get('/api/drugs')
        assert resp.status_code == 200
        drugs = resp.get_json()
        assert all(d['status'] == 'approved' for d in drugs)
