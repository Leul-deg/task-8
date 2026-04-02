from flask import Blueprint, render_template, request, redirect, flash, abort
from flask_login import login_required, current_user
from app.models.drug import Drug
from app.services.drug_service import (
    create_drug, update_drug, submit_for_approval, approve_drug,
    reject_drug, search_drugs, import_drugs,
)
from app.services.permission_service import has_permission
from app.utils.decorators import require_permission
from app.utils.constants import DrugForm, DrugStatus

drug_pages_bp = Blueprint('drug_pages', __name__, url_prefix='/drugs')


def _can_view_unapproved(user) -> bool:
    return has_permission(user, 'drug.approve') or has_permission(user, 'drug.edit')


@drug_pages_bp.route('')
@login_required
def index():
    q = request.args.get('q', '')
    form_filter = request.args.get('form')
    page = request.args.get('page', 1, type=int)
    privileged = _can_view_unapproved(current_user)
    status_filter = request.args.get('status') if privileged else None
    result = search_drugs(q, form_filter=form_filter, status_filter=status_filter, page=page)
    if request.headers.get('HX-Request'):
        return render_template('drugs/partials/drug_results.html', **result, query=q)
    return render_template('drugs/index.html', **result, query=q,
                           drug_forms=DrugForm, drug_statuses=DrugStatus, is_admin=privileged)


@drug_pages_bp.route('/new')
@login_required
@require_permission('drug.create')
def new():
    return render_template('drugs/form.html', drug=None, drug_forms=DrugForm)


@drug_pages_bp.route('', methods=['POST'])
@login_required
@require_permission('drug.create')
def create():
    data = {
        'generic_name': request.form.get('generic_name'),
        'brand_name': request.form.get('brand_name'),
        'strength': request.form.get('strength'),
        'form': request.form.get('form'),
        'ndc_code': request.form.get('ndc_code'),
        'description': request.form.get('description'),
        'contraindications': request.form.get('contraindications'),
        'side_effects': request.form.get('side_effects'),
    }
    try:
        drug = create_drug(data, current_user)
        flash('Drug entry created', 'success')
        return redirect(f'/drugs/{drug.id}')
    except ValueError as e:
        flash(str(e), 'error')
        return render_template('drugs/form.html', drug=None, drug_forms=DrugForm, form_data=data)


@drug_pages_bp.route('/<int:drug_id>')
@login_required
def detail(drug_id):
    drug = Drug.query.get_or_404(drug_id)
    if drug.status != 'approved' and not _can_view_unapproved(current_user):
        abort(403)
    return render_template('drugs/detail.html', drug=drug)


@drug_pages_bp.route('/<int:drug_id>/submit', methods=['POST'])
@login_required
def submit(drug_id):
    try:
        submit_for_approval(Drug.query.get_or_404(drug_id), current_user)
        flash('Submitted for approval', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(f'/drugs/{drug_id}')


@drug_pages_bp.route('/<int:drug_id>/approve', methods=['POST'])
@login_required
@require_permission('drug.approve')
def approve(drug_id):
    approve_drug(Drug.query.get_or_404(drug_id), current_user)
    flash('Drug approved', 'success')
    return redirect(f'/drugs/{drug_id}')


@drug_pages_bp.route('/<int:drug_id>/reject', methods=['POST'])
@login_required
@require_permission('drug.approve')
def reject(drug_id):
    reason = request.form.get('reason', '')
    try:
        reject_drug(Drug.query.get_or_404(drug_id), current_user, reason)
        flash('Drug rejected', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(f'/drugs/{drug_id}')


@drug_pages_bp.route('/import', methods=['GET', 'POST'])
@login_required
@require_permission('drug.import')
def import_csv():
    if request.method == 'GET':
        return render_template('drugs/import.html')
    file = request.files.get('csv_file')
    if not file:
        flash('No file selected', 'error')
        return render_template('drugs/import.html')
    result = import_drugs(file.stream, current_user.id)
    return render_template('drugs/import.html', result=result)
