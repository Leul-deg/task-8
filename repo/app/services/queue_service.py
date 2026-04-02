import json
import random
from datetime import datetime, timezone, timedelta
from app.extensions import db
from app.models.queue import JobQueue
from app.utils.constants import JobStatus


def enqueue(job_type: str, payload: dict, max_attempts: int = 3) -> JobQueue:
    job = JobQueue(
        job_type=job_type,
        payload=json.dumps(payload),
        status=JobStatus.PENDING.value,
        attempts=0,
        max_attempts=max_attempts,
    )
    db.session.add(job)
    db.session.commit()
    return job


def claim_next_job(job_type: str | None = None) -> JobQueue | None:
    now = datetime.now(timezone.utc)
    query = JobQueue.query.filter(
        JobQueue.status.in_([JobStatus.PENDING.value]),
        db.or_(JobQueue.next_retry_at == None, JobQueue.next_retry_at <= now),
    )
    if job_type:
        query = query.filter_by(job_type=job_type)
    job = query.order_by(JobQueue.created_at).first()
    if not job:
        return None
    job.status = JobStatus.PROCESSING.value
    job.started_at = now
    job.attempts += 1
    db.session.commit()
    return job


def complete_job(job: JobQueue) -> JobQueue:
    job.status = JobStatus.COMPLETED.value
    job.completed_at = datetime.now(timezone.utc)
    db.session.commit()
    return job


def fail_job(job: JobQueue, error_message: str, retry_delay_seconds: int = 60) -> JobQueue:
    if job.attempts >= job.max_attempts:
        job.status = JobStatus.DEAD_LETTER.value
    else:
        job.status = JobStatus.PENDING.value
        job.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=retry_delay_seconds)
    job.error_message = error_message
    db.session.commit()
    return job


def get_pending_jobs(job_type: str | None = None, limit: int = 100) -> list[JobQueue]:
    query = JobQueue.query.filter_by(status=JobStatus.PENDING.value)
    if job_type:
        query = query.filter_by(job_type=job_type)
    return query.order_by(JobQueue.created_at).limit(limit).all()


def get_job_payload(job: JobQueue) -> dict:
    return json.loads(job.payload)


JOB_HANDLERS = {}


def register_job_handler(job_type: str, handler):
    JOB_HANDLERS[job_type] = handler


def _dispatch_job(job: JobQueue):
    handler = JOB_HANDLERS.get(job.job_type)
    if not handler:
        raise ValueError(f"No handler registered for job type: {job.job_type}")
    payload = json.loads(job.payload) if job.payload else {}
    handler(payload)


def process_pending_jobs():
    """Process all pending jobs that are ready to run."""
    now = datetime.now(timezone.utc)
    jobs = JobQueue.query.filter(
        JobQueue.status == JobStatus.PENDING.value,
        db.or_(JobQueue.next_retry_at == None, JobQueue.next_retry_at <= now),
    ).order_by(JobQueue.created_at).limit(10).all()
    for job in jobs:
        job.status = JobStatus.PROCESSING.value
        job.started_at = now
        db.session.commit()
        try:
            _dispatch_job(job)
            job.status = JobStatus.COMPLETED.value
            job.completed_at = datetime.now(timezone.utc)
        except Exception as e:
            job.attempts += 1
            if job.attempts >= job.max_attempts:
                job.status = JobStatus.DEAD_LETTER.value
            else:
                job.status = JobStatus.PENDING.value
                backoff = min(5 * (2 ** job.attempts), 300) * (0.9 + random.random() * 0.2)
                job.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=backoff)
            job.error_message = str(e)
        db.session.commit()
