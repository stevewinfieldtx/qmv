import os
from celery import Celery

# Create Celery instance
celery_app = Celery('quick_music_videos')

# Configure Celery
celery_app.conf.update(
    broker_url=os.environ.get('REDIS_URL', 'redis://localhost:6379'),
    result_backend=os.environ.get('REDIS_URL', 'redis://localhost:6379'),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    # Import tasks
    imports=['phase2_worker'],
    # Task routing
    task_routes={
        'phase2_worker.process_music_generation': {'queue': 'music_generation'},
    },
    # Worker settings
    worker_concurrency=2,
    worker_max_tasks_per_child=50,
    # Task settings
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

if __name__ == '__main__':
    celery_app.start()
