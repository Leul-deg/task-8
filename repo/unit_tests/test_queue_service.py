import base64
import os
from datetime import datetime, timezone, timedelta

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


@pytest.fixture(autouse=True)
def clean_handlers():
    """Restore JOB_HANDLERS to its pre-test state so registered test handlers
    do not leak between tests."""
    from app.services import queue_service
    original = dict(queue_service.JOB_HANDLERS)
    yield
    queue_service.JOB_HANDLERS.clear()
    queue_service.JOB_HANDLERS.update(original)


# ─── Existing scheduling tests ──────────────────────────────────────────────

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


# ─── Enqueue and claim ───────────────────────────────────────────────────────

class TestEnqueueAndClaim:
    def test_enqueue_creates_pending_job(self, db):
        from app.services.queue_service import enqueue, get_job_payload
        from app.utils.constants import JobStatus

        job = enqueue('backup_run', {'user_id': 1, 'priority': 'normal'})
        assert job.id is not None
        assert job.job_type == 'backup_run'
        assert job.status == JobStatus.PENDING.value
        assert job.attempts == 0
        assert job.created_at is not None
        assert get_job_payload(job) == {'user_id': 1, 'priority': 'normal'}

    def test_enqueue_custom_max_attempts(self, db):
        from app.services.queue_service import enqueue
        from app.utils.constants import JobStatus

        job = enqueue('critical_task', {}, max_attempts=5)
        assert job.max_attempts == 5
        assert job.status == JobStatus.PENDING.value

    def test_claim_next_job_marks_processing(self, db):
        from app.services.queue_service import enqueue, claim_next_job
        from app.utils.constants import JobStatus

        enqueue('claim_task', {'key': 'value'})
        job = claim_next_job('claim_task')
        assert job is not None
        assert job.status == JobStatus.PROCESSING.value
        assert job.attempts == 1
        assert job.started_at is not None

    def test_claim_next_job_returns_none_when_empty(self, db):
        from app.services.queue_service import claim_next_job

        job = claim_next_job('nonexistent_type')
        assert job is None

    def test_claim_next_job_fifo_ordering(self, db):
        from app.services.queue_service import enqueue, claim_next_job

        first = enqueue('ordered_task', {'seq': 1})
        second = enqueue('ordered_task', {'seq': 2})

        claimed = claim_next_job('ordered_task')
        assert claimed.id == first.id

    def test_claim_skips_future_retry(self, db):
        from app.services.queue_service import enqueue, claim_next_job

        job = enqueue('retry_task', {})
        job.next_retry_at = datetime.now(timezone.utc) + timedelta(hours=1)
        _db.session.commit()

        claimed = claim_next_job('retry_task')
        assert claimed is None

    def test_claim_picks_up_past_retry(self, db):
        from app.services.queue_service import enqueue, claim_next_job
        from app.utils.constants import JobStatus

        job = enqueue('past_retry_task', {})
        job.next_retry_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        _db.session.commit()

        claimed = claim_next_job('past_retry_task')
        assert claimed is not None
        assert claimed.status == JobStatus.PROCESSING.value


# ─── Job lifecycle ────────────────────────────────────────────────────────────

class TestJobLifecycle:
    def test_complete_job_sets_completed_status(self, db):
        from app.services.queue_service import enqueue, claim_next_job, complete_job
        from app.utils.constants import JobStatus

        enqueue('complete_test', {})
        job = claim_next_job('complete_test')
        result = complete_job(job)
        assert result.status == JobStatus.COMPLETED.value
        assert result.completed_at is not None

    def test_fail_job_retries_when_attempts_remaining(self, db):
        from app.services.queue_service import enqueue, claim_next_job, fail_job
        from app.utils.constants import JobStatus

        enqueue('fail_retry', {}, max_attempts=3)
        job = claim_next_job('fail_retry')  # attempts → 1
        result = fail_job(job, 'transient error')
        # attempts=1 < max_attempts=3 → back to PENDING with backoff
        assert result.status == JobStatus.PENDING.value
        assert result.error_message == 'transient error'
        assert result.next_retry_at is not None

    def test_fail_job_dead_letters_when_max_attempts_reached(self, db):
        from app.services.queue_service import enqueue, claim_next_job, fail_job
        from app.utils.constants import JobStatus

        enqueue('dead_task', {}, max_attempts=1)
        job = claim_next_job('dead_task')  # attempts → 1
        result = fail_job(job, 'permanent failure')
        # attempts=1 == max_attempts=1 → DEAD_LETTER
        assert result.status == JobStatus.DEAD_LETTER.value
        assert result.error_message == 'permanent failure'

    def test_fail_job_does_not_set_retry_when_dead_lettered(self, db):
        from app.services.queue_service import enqueue, claim_next_job, fail_job
        from app.utils.constants import JobStatus

        enqueue('no_retry_dead', {}, max_attempts=1)
        job = claim_next_job('no_retry_dead')
        result = fail_job(job, 'done')
        assert result.status == JobStatus.DEAD_LETTER.value
        # next_retry_at is not set for dead-lettered jobs
        assert result.next_retry_at is None


# ─── Query helpers ────────────────────────────────────────────────────────────

class TestJobQueries:
    def test_get_pending_jobs_returns_only_pending(self, db):
        from app.services.queue_service import enqueue, claim_next_job, get_pending_jobs
        from app.utils.constants import JobStatus

        enqueue('query_task', {'n': 1})
        enqueue('query_task', {'n': 2})
        enqueue('query_task', {'n': 3})
        claim_next_job('query_task')  # first one → PROCESSING

        pending = get_pending_jobs('query_task')
        assert all(j.status == JobStatus.PENDING.value for j in pending)
        assert len(pending) == 2

    def test_get_pending_jobs_no_type_filter_returns_all(self, db):
        from app.services.queue_service import enqueue, get_pending_jobs

        enqueue('type_a', {})
        enqueue('type_b', {})
        all_pending = get_pending_jobs()
        types = {j.job_type for j in all_pending}
        assert 'type_a' in types
        assert 'type_b' in types

    def test_get_job_payload_deserializes_json(self, db):
        from app.services.queue_service import enqueue, get_job_payload

        job = enqueue('payload_test', {'nested': {'x': 1}, 'list': [1, 2, 3]})
        payload = get_job_payload(job)
        assert payload == {'nested': {'x': 1}, 'list': [1, 2, 3]}

    def test_has_pending_job_true_for_pending(self, db):
        from app.services.queue_service import enqueue, has_pending_job

        enqueue('check_pending', {})
        assert has_pending_job('check_pending') is True

    def test_has_pending_job_true_for_processing(self, db):
        from app.services.queue_service import enqueue, claim_next_job, has_pending_job

        enqueue('check_processing', {})
        claim_next_job('check_processing')  # → PROCESSING
        assert has_pending_job('check_processing') is True

    def test_has_pending_job_false_when_empty(self, db):
        from app.services.queue_service import has_pending_job

        assert has_pending_job('absent_task') is False

    def test_has_pending_job_false_after_completion(self, db):
        from app.services.queue_service import enqueue, claim_next_job, complete_job, has_pending_job

        enqueue('done_task', {})
        job = claim_next_job('done_task')
        complete_job(job)
        assert has_pending_job('done_task') is False

    def test_has_recent_or_active_job_true_for_pending(self, db):
        from app.services.queue_service import enqueue, has_recent_or_active_job

        enqueue('recent_check', {})
        assert has_recent_or_active_job('recent_check', 3600) is True

    def test_has_recent_or_active_job_false_for_old_completed(self, db):
        from app.services.queue_service import enqueue, claim_next_job, complete_job, has_recent_or_active_job
        from app.models.queue import JobQueue

        enqueue('old_done', {})
        job = claim_next_job('old_done')
        complete_job(job)
        # Backdate completed_at and created_at so it falls outside the window
        job.completed_at = datetime.now(timezone.utc) - timedelta(hours=2)
        job.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
        _db.session.commit()

        assert has_recent_or_active_job('old_done', 60) is False


# ─── Full dispatch cycle ──────────────────────────────────────────────────────

class TestJobDispatch:
    def test_process_pending_jobs_dispatches_registered_handler(self, db):
        from app.services.queue_service import enqueue, register_job_handler, process_pending_jobs

        results = []

        def handle_dispatch_test(payload):
            results.append(payload)

        register_job_handler('dispatch_test_unique', handle_dispatch_test)
        enqueue('dispatch_test_unique', {'message': 'hello'})
        process_pending_jobs()

        assert len(results) == 1
        assert results[0] == {'message': 'hello'}

    def test_process_pending_jobs_marks_job_completed(self, db):
        from app.services.queue_service import enqueue, register_job_handler, process_pending_jobs
        from app.models.queue import JobQueue
        from app.utils.constants import JobStatus

        register_job_handler('complete_dispatch_unique', lambda p: None)
        enqueue('complete_dispatch_unique', {})
        process_pending_jobs()

        job = JobQueue.query.filter_by(job_type='complete_dispatch_unique').first()
        assert job.status == JobStatus.COMPLETED.value
        assert job.completed_at is not None

    def test_process_pending_jobs_retries_on_transient_failure(self, db):
        from app.services.queue_service import enqueue, register_job_handler, process_pending_jobs
        from app.models.queue import JobQueue
        from app.utils.constants import JobStatus

        def flaky_handler(payload):
            raise RuntimeError('temporary error')

        register_job_handler('flaky_task_unique', flaky_handler)
        enqueue('flaky_task_unique', {}, max_attempts=3)
        process_pending_jobs()

        job = JobQueue.query.filter_by(job_type='flaky_task_unique').first()
        # 1 attempt used of 3 → stays PENDING with backoff
        assert job.status == JobStatus.PENDING.value
        assert 'temporary error' in job.error_message
        assert job.next_retry_at is not None

    def test_process_pending_jobs_dead_letters_after_max_attempts(self, db):
        from app.services.queue_service import enqueue, register_job_handler, process_pending_jobs
        from app.models.queue import JobQueue
        from app.utils.constants import JobStatus

        def always_fails(payload):
            raise ValueError('permanent error')

        register_job_handler('dead_letter_unique', always_fails)
        enqueue('dead_letter_unique', {}, max_attempts=1)
        process_pending_jobs()

        job = JobQueue.query.filter_by(job_type='dead_letter_unique').first()
        assert job.status == JobStatus.DEAD_LETTER.value
        assert 'permanent error' in job.error_message

    def test_process_pending_jobs_unregistered_type_eventually_dead_letters(self, db):
        from app.services.queue_service import enqueue, process_pending_jobs
        from app.models.queue import JobQueue
        from app.utils.constants import JobStatus

        enqueue('totally_unknown_type', {}, max_attempts=1)
        process_pending_jobs()

        job = JobQueue.query.filter_by(job_type='totally_unknown_type').first()
        # No handler → ValueError → dead-lettered after 1 attempt
        assert job.status == JobStatus.DEAD_LETTER.value
        assert 'No handler registered' in job.error_message

    def test_process_pending_jobs_processes_multiple_jobs(self, db):
        from app.services.queue_service import enqueue, register_job_handler, process_pending_jobs
        from app.models.queue import JobQueue
        from app.utils.constants import JobStatus

        call_count = [0]

        def counter_handler(payload):
            call_count[0] += 1

        register_job_handler('multi_dispatch_unique', counter_handler)
        enqueue('multi_dispatch_unique', {'n': 1})
        enqueue('multi_dispatch_unique', {'n': 2})
        enqueue('multi_dispatch_unique', {'n': 3})
        process_pending_jobs()

        assert call_count[0] == 3
        completed = JobQueue.query.filter_by(
            job_type='multi_dispatch_unique',
            status=JobStatus.COMPLETED.value,
        ).count()
        assert completed == 3
