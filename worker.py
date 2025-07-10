```python
#!/usr/bin/env python3
"""
Celery worker for background tasks
"""
import os
import sys
import logging
from celery_app import celery_app

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    logger.info("Starting Celery worker for Quick Music Videos")
    
    # Start Celery worker
    celery_app.worker_main([
        'worker',
        '--loglevel=info',
        '--concurrency=2',
        '--queues=music_generation,celery'
    ])
```
