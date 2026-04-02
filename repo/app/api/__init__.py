from app.api.auth_routes import auth_bp
from app.api.listing_routes import listing_bp
from app.api.listing_page_routes import listing_pages_bp
from app.api.review_routes import review_bp
from app.api.moderation_routes import moderation_bp
from app.api.drug_routes import drug_bp
from app.api.admin_routes import admin_bp
from app.api.page_routes import pages_bp
from app.api.class_page_routes import class_pages_bp
from app.api.class_routes import class_bp
from app.api.moderation_page_routes import moderation_pages_bp
from app.api.drug_page_routes import drug_pages_bp


def register_blueprints(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(listing_bp)
    app.register_blueprint(listing_pages_bp)
    app.register_blueprint(review_bp)
    app.register_blueprint(moderation_bp)
    app.register_blueprint(drug_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(class_pages_bp)
    app.register_blueprint(class_bp)
    app.register_blueprint(moderation_pages_bp)
    app.register_blueprint(drug_pages_bp)
