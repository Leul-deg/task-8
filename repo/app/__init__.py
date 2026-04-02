from flask import Flask, jsonify, render_template, request, redirect, g, send_from_directory, session
from flask_login import current_user
from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3
import uuid
from app.config import config_map
from app.extensions import db, login_manager, csrf


def create_app(config_name: str = 'development') -> Flask:
    app = Flask(__name__)
    config_class = config_map.get(config_name, config_map['development'])
    app.config.from_object(config_class)

    _configure_sqlite_pragmas()
    _init_extensions(app)
    _validate_encryption_config(app)
    _register_blueprints(app)
    _register_error_handlers(app)
    _register_before_request_hooks(app)
    _register_template_filters(app)
    _register_cli(app)

    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect('/dashboard')
        return redirect('/auth/login')

    @app.route('/sw.js')
    def service_worker():
        resp = send_from_directory(app.static_folder, 'js/sw.js',
                                   mimetype='application/javascript')
        resp.headers['Service-Worker-Allowed'] = '/'
        resp.headers['Cache-Control'] = 'no-cache'
        return resp

    from app.services.queue_service import register_job_handler
    from app.services.listing_service import expire_stale_listings
    from app.services.permission_service import expire_temp_grants
    register_job_handler('expire_listings', lambda p: expire_stale_listings())
    register_job_handler('expire_grants', lambda p: expire_temp_grants())

    return app


def _validate_encryption_config(app: Flask):
    if not app.config.get('TESTING') and not app.config.get('ENCRYPTION_KEY'):
        raise RuntimeError(
            'ENCRYPTION_KEY must be set in non-test environments. '
            'Generate one with: python -c "from app.utils.crypto import generate_key; print(generate_key())"'
        )


def _configure_sqlite_pragmas():
    @event.listens_for(Engine, 'connect')
    def set_sqlite_pragma(dbapi_conn, connection_record):
        if isinstance(dbapi_conn, sqlite3.Connection):
            cursor = dbapi_conn.cursor()
            cursor.execute('PRAGMA journal_mode=WAL')
            cursor.execute('PRAGMA foreign_keys=ON')
            cursor.close()


def _init_extensions(app: Flask):
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({'error': 'Authentication required'}), 401
        return render_template('auth/login.html'), 401


def _register_blueprints(app: Flask):
    from app.api import register_blueprints
    register_blueprints(app)


def _register_error_handlers(app: Flask):
    def is_api_request() -> bool:
        return request.path.startswith('/api/') or request.is_json

    @app.errorhandler(400)
    def bad_request(e):
        if is_api_request():
            return jsonify({'error': 'Bad request', 'detail': str(e)}), 400
        return render_template('errors/400.html'), 400

    @app.errorhandler(401)
    def unauthorized(e):
        if is_api_request():
            return jsonify({'error': 'Unauthorized'}), 401
        return render_template('errors/401.html'), 401

    @app.errorhandler(403)
    def forbidden(e):
        if is_api_request():
            return jsonify({'error': 'Forbidden'}), 403
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        if is_api_request():
            return jsonify({'error': 'Not found'}), 404
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        if is_api_request():
            return jsonify({'error': 'Internal server error'}), 500
        return render_template('errors/500.html'), 500


def _register_before_request_hooks(app: Flask):
    @app.before_request
    def set_request_id():
        g.request_id = str(uuid.uuid4())
        g.ip_address = request.remote_addr

    @app.before_request
    def expire_temp_grants():
        from app.services.permission_service import expire_temp_grants as do_expire
        try:
            do_expire()
        except Exception:
            app.logger.exception('expire_temp_grants failed')

    @app.before_request
    def ensure_browser_hmac_secret():
        if current_user.is_authenticated and not session.get('hmac_client_secret'):
            session['hmac_client_secret'] = uuid.uuid4().hex + uuid.uuid4().hex

    @app.after_request
    def set_security_headers(response):
        if current_user.is_authenticated and not request.path.startswith('/static/'):
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
        return response


def _register_template_filters(app: Flask):
    from app.utils.masking import mask_field, get_mask_type_for_role
    app.jinja_env.filters['mask'] = mask_field

    @app.template_filter('mask_for_role')
    def mask_for_role(value, field_type='email'):
        if not value:
            return value
        if current_user.is_authenticated:
            mask_type = get_mask_type_for_role(current_user.roles, field_type)
            if mask_type == 'none':
                return value
            return mask_field(str(value), mask_type)
        return mask_field(str(value), 'full')

    @app.template_filter('format_usd')
    def format_usd(cents):
        if cents is None:
            return '$0.00'
        return f'${cents / 100:,.2f}'

    @app.template_filter('format_date')
    def format_date(dt):
        if dt is None:
            return ''
        if hasattr(dt, 'strftime'):
            return dt.strftime('%b %d, %Y')
        return str(dt)

    @app.context_processor
    def inject_hmac_client_secret():
        if current_user.is_authenticated:
            return {'hmac_client_secret': session.get('hmac_client_secret', '')}
        return {'hmac_client_secret': ''}


def _register_cli(app: Flask):
    @app.cli.command('db-init')
    def db_init():
        """Initialize the database and create FTS tables."""
        db.create_all()
        _create_fts_table(db)
        print('Database initialized.')

    @app.cli.command('db-seed')
    def db_seed():
        """Seed default data."""
        from scripts.seed_data import seed
        seed()
        print('Database seeded.')

    @app.cli.command('db-backup')
    def db_backup():
        """Create a database backup."""
        import os
        from app.services.backup_service import create_backup, prune_old_backups
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        db_path = db_uri.replace('sqlite:///', '')
        backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
        path = create_backup(db_path, backup_dir)
        prune_old_backups(backup_dir)
        print(f'Backup created: {path}')


def _create_fts_table(db_instance):
    """Create SQLite FTS5 virtual table for Drug full-text search."""
    sql_statements = [
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS drug_fts
        USING fts5(
            generic_name,
            brand_name,
            description,
            contraindications,
            side_effects,
            content='drug',
            content_rowid='id'
        )
        """,
        """
        CREATE TRIGGER IF NOT EXISTS drug_ai AFTER INSERT ON drug BEGIN
            INSERT INTO drug_fts(rowid, generic_name, brand_name, description, contraindications, side_effects)
            VALUES (new.id, new.generic_name, new.brand_name, new.description, new.contraindications, new.side_effects);
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS drug_au AFTER UPDATE ON drug BEGIN
            INSERT INTO drug_fts(drug_fts, rowid, generic_name, brand_name, description, contraindications, side_effects)
            VALUES ('delete', old.id, old.generic_name, old.brand_name, old.description, old.contraindications, old.side_effects);
            INSERT INTO drug_fts(rowid, generic_name, brand_name, description, contraindications, side_effects)
            VALUES (new.id, new.generic_name, new.brand_name, new.description, new.contraindications, new.side_effects);
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS drug_ad AFTER DELETE ON drug BEGIN
            INSERT INTO drug_fts(drug_fts, rowid, generic_name, brand_name, description, contraindications, side_effects)
            VALUES ('delete', old.id, old.generic_name, old.brand_name, old.description, old.contraindications, old.side_effects);
        END
        """,
    ]
    with db_instance.engine.connect() as conn:
        for stmt in sql_statements:
            conn.execute(db_instance.text(stmt))
        conn.commit()
