import os
from app.utils.constants import (
    MAX_CONTENT_LENGTH,
    TEMP_GRANT_DEFAULT_HOURS,
    REVIEW_APPEAL_WINDOW_DAYS,
    APPEAL_RESOLUTION_DAYS,
    BACKUP_RETENTION_DAYS,
    HMAC_WINDOW_SECONDS,
)


class BaseConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    MAX_CONTENT_LENGTH = MAX_CONTENT_LENGTH
    HMAC_SECRET = os.environ.get('HMAC_SECRET', 'dev-hmac-secret-change-in-prod')
    HMAC_WINDOW_SECONDS = HMAC_WINDOW_SECONDS
    # Login rate limiting — max failures within the window per axis (0 = disabled)
    LOGIN_MAX_ATTEMPTS_PER_IP = 20
    LOGIN_MAX_ATTEMPTS_PER_USERNAME = 10
    LOGIN_RATE_WINDOW_SECONDS = 900  # 15 minutes
    ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY', '')
    BACKUP_RETENTION_DAYS = BACKUP_RETENTION_DAYS
    TEMP_GRANT_DEFAULT_HOURS = TEMP_GRANT_DEFAULT_HOURS
    REVIEW_APPEAL_WINDOW_DAYS = REVIEW_APPEAL_WINDOW_DAYS
    APPEAL_RESOLUTION_DAYS = APPEAL_RESOLUTION_DAYS
    REVIEWER_DISPLAY_MODE = os.environ.get('REVIEWER_DISPLAY_MODE', 'anonymous')
    WTF_CSRF_ENABLED = True


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 'sqlite:///dev.db'
    )


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    LOGIN_MAX_ATTEMPTS_PER_IP = 0
    LOGIN_MAX_ATTEMPTS_PER_USERNAME = 0


class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SESSION_COOKIE_SECURE = True


config_map = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
}
