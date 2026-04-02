from flask import Blueprint, request, jsonify, make_response, render_template, redirect, flash, session
from flask_login import current_user, login_required
from app.services.auth_service import register_user, authenticate_user, logout_current_user, change_password, RateLimitError
from app.models.organization import OrgUnit

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


# ── Browser page routes ────────────────────────────────────────────────────

@auth_bp.route('/login', methods=['GET'])
def login_page():
    if current_user.is_authenticated:
        return redirect('/dashboard')
    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET'])
def register_page():
    if current_user.is_authenticated:
        return redirect('/dashboard')
    orgs = OrgUnit.query.filter_by(is_active=True).all()
    return render_template('auth/register.html', org_units=orgs)


# ── Auth API / form handlers ───────────────────────────────────────────────

@auth_bp.route('/register', methods=['POST'])
def register():
    is_form = bool(request.form)
    data = request.form if is_form else (request.get_json(silent=True) or {})

    username = data.get('username', '').strip()
    password = data.get('password', '')
    email = data.get('email', '').strip() or None
    full_name = data.get('full_name', '').strip() or None

    if not username or not password:
        msg = 'username and password are required'
        if is_form:
            flash(msg, 'error')
            orgs = OrgUnit.query.filter_by(is_active=True).all()
            return render_template('auth/register.html', org_units=orgs), 400
        return jsonify({'error': msg}), 400

    if is_form:
        confirm = data.get('confirm_password', '')
        if password != confirm:
            flash('Passwords do not match', 'error')
            orgs = OrgUnit.query.filter_by(is_active=True).all()
            return render_template('auth/register.html', org_units=orgs), 400

    org_unit_ids = []
    raw_org = data.get('org_unit_id')
    if raw_org:
        try:
            org_unit_ids = [int(raw_org)]
        except (TypeError, ValueError):
            pass

    try:
        user = register_user(
            username=username,
            password=password,
            email=email,
            full_name=full_name,
            org_unit_ids=org_unit_ids or None,
        )
    except ValueError as e:
        if is_form:
            flash(str(e), 'error')
            orgs = OrgUnit.query.filter_by(is_active=True).all()
            return render_template('auth/register.html', org_units=orgs), 400
        status = 409 if 'already' in str(e) else 400
        return jsonify({'error': str(e)}), status

    if is_form:
        flash('Account created. Please sign in.', 'success')
        return redirect('/auth/login')
    return jsonify(user.to_dict()), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    is_form = bool(request.form)
    data = request.form if is_form else (request.get_json(silent=True) or {})

    try:
        user = authenticate_user(
            username=data.get('username', ''),
            password=data.get('password', ''),
            ip_address=request.remote_addr,
        )
    except RateLimitError as e:
        if is_form:
            flash(str(e), 'error')
            return render_template('auth/login.html'), 429
        return jsonify({'error': str(e)}), 429

    if not user:
        if is_form:
            flash('Invalid credentials', 'error')
            return render_template('auth/login.html'), 401
        return jsonify({'error': 'Invalid credentials'}), 401

    if is_form:
        flash('Welcome back!', 'success')
        return redirect('/dashboard')
    return jsonify(user.to_dict()), 200


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_current_user(user_id=current_user.id)
    session.pop('hmac_client_secret', None)
    is_htmx = request.headers.get('HX-Request')

    if is_htmx:
        resp = make_response(jsonify({'message': 'Logged out'}), 200)
        resp.headers['HX-Trigger'] = 'clearSwCache'
    else:
        resp = make_response(jsonify({'message': 'Logged out'}), 200)

    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Clear-Site-Data'] = '"cache"'
    return resp


@auth_bp.route('/me', methods=['GET'])
@login_required
def me():
    return jsonify(current_user.to_dict()), 200


@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_pw():
    data = request.get_json(silent=True) or {}
    try:
        change_password(current_user, data.get('old_password', ''), data.get('new_password', ''))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'message': 'Password updated'}), 200
