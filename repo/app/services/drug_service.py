from datetime import datetime, timezone
from app.extensions import db
from app.models.drug import Drug, TagTaxonomy
from app.models.user import User
from app.utils.constants import DrugStatus, DrugForm
from app.services.audit_service import log_action
from app.services.permission_service import has_permission
from app.utils.validators import validate_ndc_code


def create_drug(data: dict, created_by: User) -> Drug:
    form = (data.get('form') or '').strip().lower()
    if form not in [f.value for f in DrugForm]:
        raise ValueError(f"Invalid form: {form}")
    ndc_code = validate_ndc_code(data.get('ndc_code'))
    existing = Drug.query.filter_by(
        generic_name=data['generic_name'],
        strength=data['strength'],
        form=form,
    ).first()
    if existing:
        raise ValueError("A drug with the same generic name, strength, and form already exists")
    drug = Drug(
        generic_name=data['generic_name'],
        brand_name=data.get('brand_name'),
        strength=data['strength'],
        form=form,
        ndc_code=ndc_code,
        description=data.get('description'),
        contraindications=data.get('contraindications'),
        side_effects=data.get('side_effects'),
        status=DrugStatus.DRAFT.value,
        created_by_id=created_by.id,
    )
    db.session.add(drug)
    db.session.flush()
    for tag_name in data.get('tags', []):
        tag = TagTaxonomy.query.filter_by(name=tag_name).first()
        if not tag:
            raise ValueError(f"Unknown taxonomy tag: {tag_name}")
        drug.tags.append(tag)
    db.session.commit()
    log_action(
        action='drug.create',
        resource_type='drug',
        resource_id=drug.id,
        user_id=created_by.id,
        new_value=drug.to_dict(),
    )
    return drug


def update_drug(drug: Drug, data: dict, updated_by: User) -> Drug:
    old = drug.to_dict()
    updatable = ['brand_name', 'ndc_code', 'description', 'contraindications', 'side_effects']
    for field in updatable:
        if field in data:
            if field == 'ndc_code':
                setattr(drug, field, validate_ndc_code(data[field]))
            else:
                setattr(drug, field, data[field])
    if 'tags' in data:
        tags = []
        for tag_name in data.get('tags', []):
            tag = TagTaxonomy.query.filter_by(name=tag_name).first()
            if not tag:
                raise ValueError(f"Unknown taxonomy tag: {tag_name}")
            tags.append(tag)
        drug.tags = tags
    drug.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    log_action(
        action='drug.update',
        resource_type='drug',
        resource_id=drug.id,
        user_id=updated_by.id,
        old_value=old,
        new_value=drug.to_dict(),
    )
    return drug


def submit_for_approval(drug: Drug, submitted_by: User) -> Drug:
    if drug.status != DrugStatus.DRAFT.value:
        raise ValueError("Only draft drugs can be submitted for approval")
    role_count = submitted_by.roles.count() if hasattr(submitted_by.roles, 'count') else len(submitted_by.roles)
    if role_count == 0 and drug.created_by_id == submitted_by.id:
        pass
    elif not (
        has_permission(submitted_by, 'drug.create') or
        has_permission(submitted_by, 'drug.edit') or
        has_permission(submitted_by, 'drug.approve')
    ):
        raise PermissionError("You do not have permission to submit drug entries")
    if drug.created_by_id != submitted_by.id and not has_permission(submitted_by, 'drug.approve'):
        raise PermissionError("Only the creator or an approver can submit this drug")
    drug.status = DrugStatus.PENDING_APPROVAL.value
    drug.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    log_action(
        action='drug.submit',
        resource_type='drug',
        resource_id=drug.id,
        user_id=submitted_by.id,
    )
    return drug


def approve_drug(drug: Drug, approved_by: User) -> Drug:
    if drug.status != DrugStatus.PENDING_APPROVAL.value:
        raise ValueError("Only pending drugs can be approved")
    now = datetime.now(timezone.utc)
    drug.status = DrugStatus.APPROVED.value
    drug.approved_by_id = approved_by.id
    drug.approved_at = now
    drug.updated_at = now
    db.session.commit()
    log_action(
        action='drug.approve',
        resource_type='drug',
        resource_id=drug.id,
        user_id=approved_by.id,
    )
    return drug


def reject_drug(drug: Drug, rejected_by: User, reason: str) -> Drug:
    if drug.status != DrugStatus.PENDING_APPROVAL.value:
        raise ValueError("Only pending drugs can be rejected")
    drug.status = DrugStatus.REJECTED.value
    drug.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    log_action(
        action='drug.reject',
        resource_type='drug',
        resource_id=drug.id,
        user_id=rejected_by.id,
        new_value={'reason': reason},
    )
    return drug


def search_drugs(query_text: str = '', form_filter: str = None,
                 status_filter: str = None, page: int = 1, per_page: int = 20):
    from app.extensions import db as _db
    if query_text and query_text.strip():
        safe_query = query_text.replace('"', '""')
        sql = """
            SELECT drug.*, snippet(drug_fts, 0, '<mark>', '</mark>', '...', 30) as snippet_text
            FROM drug
            JOIN drug_fts ON drug.id = drug_fts.rowid
            WHERE drug_fts MATCH :q
        """
        params = {'q': f'"{safe_query}"'}
        if form_filter:
            sql += " AND drug.form = :form"
            params['form'] = form_filter
        if status_filter:
            sql += " AND drug.status = :status"
            params['status'] = status_filter
        else:
            sql += " AND drug.status = 'approved'"
        sql += " ORDER BY rank LIMIT :limit OFFSET :offset"
        params['limit'] = per_page
        params['offset'] = (page - 1) * per_page
        result = _db.session.execute(_db.text(sql), params)
        rows = result.fetchall()
        drugs = []
        for row in rows:
            drug = db.session.get(Drug, row[0])
            drugs.append({'drug': drug, 'snippet': row[-1] if row[-1] else ''})
        return {'items': drugs, 'total': len(drugs), 'page': page}
    else:
        query = Drug.query
        if form_filter:
            query = query.filter_by(form=form_filter)
        if status_filter:
            query = query.filter_by(status=status_filter)
        else:
            query = query.filter_by(status='approved')
        total = query.count()
        drugs = query.order_by(Drug.generic_name).offset((page - 1) * per_page).limit(per_page).all()
        return {'items': [{'drug': d, 'snippet': ''} for d in drugs], 'total': total, 'page': page}


def import_drugs(file_stream, user_id: int) -> dict:
    import csv, io
    reader = csv.DictReader(io.TextIOWrapper(file_stream, encoding='utf-8'))
    imported, skipped, errors = 0, 0, []
    for i, row in enumerate(reader, start=2):
        try:
            gn = row.get('generic_name', '').strip()
            strength = row.get('strength', '').strip()
            form = row.get('form', '').strip().lower()
            if not gn or not strength or not form:
                errors.append({'row': i, 'error': 'Missing required field (generic_name, strength, or form)'})
                continue
            if form not in [f.value for f in DrugForm]:
                errors.append({'row': i, 'error': f'Invalid form: {form}'})
                continue
            exists = Drug.query.filter(
                db.func.lower(Drug.generic_name) == gn.lower(),
                db.func.lower(Drug.strength) == strength.lower(),
                Drug.form == form,
            ).first()
            if exists:
                skipped += 1
                continue
            drug = Drug(
                generic_name=gn,
                brand_name=row.get('brand_name', '').strip() or None,
                strength=strength,
                form=form,
                ndc_code=row.get('ndc_code', '').strip() or None,
                description=row.get('description', '').strip() or None,
                contraindications=row.get('contraindications', '').strip() or None,
                side_effects=row.get('side_effects', '').strip() or None,
                status=DrugStatus.DRAFT.value,
                created_by_id=user_id,
            )
            db.session.add(drug)
            imported += 1
        except Exception as e:
            errors.append({'row': i, 'error': str(e)})
    if imported > 0:
        db.session.commit()
    log_action(
        action='drug.bulk_import',
        resource_type='drug',
        resource_id=None,
        user_id=user_id,
        new_value={'imported': imported, 'skipped': skipped, 'errors': len(errors)},
    )
    return {'imported': imported, 'skipped': skipped, 'errors': errors}
