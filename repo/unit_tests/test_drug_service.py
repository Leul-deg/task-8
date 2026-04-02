import io
import pytest
from app import create_app
from app.extensions import db as _db
from app.models.user import User
from app.services.drug_service import create_drug, update_drug, submit_for_approval, approve_drug, reject_drug, search_drugs, import_drugs
from app.utils.constants import DrugStatus, DrugForm


@pytest.fixture(scope='function')
def app():
    application = create_app('testing')
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def db(app):
    return _db


def _setup(db):
    user = User(username='pharmacist', email='rx@test.com')
    user.set_password('pass')
    _db.session.add(user)
    _db.session.commit()
    return user


def _drug_data():
    return {
        'generic_name': 'Metformin',
        'strength': '500mg',
        'form': DrugForm.TABLET.value,
        'description': 'Biguanide antidiabetic',
    }


class TestCreateDrug:
    def test_creates_drug(self, db):
        user = _setup(db)
        drug = create_drug(_drug_data(), user)
        assert drug.id is not None
        assert drug.status == DrugStatus.DRAFT.value

    def test_duplicate_raises(self, db):
        user = _setup(db)
        create_drug(_drug_data(), user)
        with pytest.raises(ValueError, match='already exists'):
            create_drug(_drug_data(), user)


class TestDrugWorkflow:
    def test_submit_for_approval(self, db):
        user = _setup(db)
        drug = create_drug(_drug_data(), user)
        drug = submit_for_approval(drug, user)
        assert drug.status == DrugStatus.PENDING_APPROVAL.value

    def test_approve_drug(self, db):
        user = _setup(db)
        drug = create_drug(_drug_data(), user)
        submit_for_approval(drug, user)
        drug = approve_drug(drug, user)
        assert drug.status == DrugStatus.APPROVED.value
        assert drug.approved_by_id == user.id
        assert drug.approved_at is not None

    def test_reject_drug(self, db):
        user = _setup(db)
        drug = create_drug(_drug_data(), user)
        submit_for_approval(drug, user)
        drug = reject_drug(drug, user, 'Incomplete data')
        assert drug.status == DrugStatus.REJECTED.value

    def test_cannot_approve_draft(self, db):
        user = _setup(db)
        drug = create_drug(_drug_data(), user)
        with pytest.raises(ValueError, match='pending'):
            approve_drug(drug, user)

    def test_cannot_submit_non_draft(self, db):
        user = _setup(db)
        drug = create_drug(_drug_data(), user)
        submit_for_approval(drug, user)
        with pytest.raises(ValueError, match='draft'):
            submit_for_approval(drug, user)


class TestDrugDuplicate:
    def test_create_drug_duplicate_exact_match(self, db):
        """Duplicate check on exact generic_name, strength, and form."""
        user = _setup(db)
        create_drug(_drug_data(), user)
        with pytest.raises(ValueError, match='already exists'):
            create_drug(_drug_data(), user)

    def test_create_drug_different_strength_allowed(self, db):
        """Same generic_name but different strength is not a duplicate."""
        user = _setup(db)
        create_drug(_drug_data(), user)
        data2 = {**_drug_data(), 'strength': '1000mg'}
        drug2 = create_drug(data2, user)
        assert drug2.id is not None


class TestDrugSearch:
    def test_search_returns_results_no_query(self, db):
        user = _setup(db)
        drug = create_drug(_drug_data(), user)
        submit_for_approval(drug, user)
        approve_drug(drug, user)
        result = search_drugs(status_filter=DrugStatus.APPROVED.value)
        assert result['total'] >= 1
        assert any(item['drug'].id == drug.id for item in result['items'])

    def test_search_with_status_filter(self, db):
        user = _setup(db)
        create_drug(_drug_data(), user)  # left in draft
        result = search_drugs(status_filter=DrugStatus.DRAFT.value)
        assert result['total'] == 1

    def test_search_with_form_filter(self, db):
        user = _setup(db)
        tablet = create_drug(_drug_data(), user)
        submit_for_approval(tablet, user)
        approve_drug(tablet, user)
        result = search_drugs(form_filter=DrugForm.CAPSULE.value, status_filter=DrugStatus.APPROVED.value)
        assert result['total'] == 0


class TestDrugImport:
    def test_import_csv_success(self, db):
        user = _setup(db)
        csv_content = (
            b"generic_name,strength,form,description\n"
            b"Aspirin,100mg,tablet,Pain reliever\n"
            b"Ibuprofen,200mg,tablet,Anti-inflammatory\n"
        )
        result = import_drugs(io.BytesIO(csv_content), user.id)
        assert result['imported'] == 2
        assert result['skipped'] == 0
        assert result['errors'] == []

    def test_import_csv_skips_duplicates(self, db):
        user = _setup(db)
        create_drug({'generic_name': 'Aspirin', 'strength': '100mg', 'form': 'tablet'}, user)
        csv_content = b"generic_name,strength,form\nAspirin,100mg,tablet\n"
        result = import_drugs(io.BytesIO(csv_content), user.id)
        assert result['skipped'] == 1
        assert result['imported'] == 0

    def test_import_csv_invalid_form(self, db):
        user = _setup(db)
        csv_content = b"generic_name,strength,form\nBadDrug,10mg,spray\n"
        result = import_drugs(io.BytesIO(csv_content), user.id)
        assert result['imported'] == 0
        assert len(result['errors']) == 1

    def test_import_csv_missing_field(self, db):
        user = _setup(db)
        csv_content = b"generic_name,strength\nNoDrug,5mg\n"
        result = import_drugs(io.BytesIO(csv_content), user.id)
        assert result['imported'] == 0
        assert len(result['errors']) == 1
