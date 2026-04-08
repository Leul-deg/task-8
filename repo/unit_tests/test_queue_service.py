import base64
import os

import pytest

from app import create_app
from app.extensions import db as _db


@pytest.fixture(scope='function')
def app(tmp_path):
    application = create_app('testing')
    application.config['ENCRYPTION_KEY'] = base64.b64encode(os.urandom(32)).decode()
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def db(app):
    return _db


class TestQueueScheduling:
    def test_schedule_default_jobs_includes_nightly_backup(self, db):
        from app.services.queue_service import schedule_default_jobs
        from app.models.queue import JobQueue

        schedule_default_jobs()
        job_types = {job.job_type for job in JobQueue.query.all()}
        assert 'nightly_backup' in job_types
        assert 'expire_listings' in job_types
        assert 'expire_grants' in job_types

    def test_schedule_default_jobs_does_not_duplicate_recent_jobs(self, db):
        from app.services.queue_service import schedule_default_jobs
        from app.models.queue import JobQueue

        schedule_default_jobs()
        first_count = JobQueue.query.count()
        schedule_default_jobs()
        second_count = JobQueue.query.count()
        assert first_count == second_count
