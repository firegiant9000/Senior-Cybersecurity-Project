# Background Workers

Placeholder directory for background job processing.

## Options

### APScheduler (Recommended for single-server)

```bash
pip install apscheduler
```

```python
# app/workers/ingest_jobs.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('interval', hours=1)
async def ingest_cisa_kev():
    # Fetch and store data
    pass

# In app/main.py
@app.on_event("startup")
async def startup():
    scheduler.start()
```

### Celery (For distributed workers)

```bash
pip install celery redis
```

```python
# app/workers/celery_app.py
from celery import Celery

celery_app = Celery(
    "cyber_threat",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
)

@celery_app.task
async def ingest_cisa_kev():
    pass
```

### FastAPI BackgroundTasks (For simple jobs)

```python
from fastapi import BackgroundTasks

@app.post("/api/v1/ingest/cisa-kev")
async def trigger_cisa_kev(background_tasks: BackgroundTasks):
    background_tasks.add_task(ingest_cisa_kev)
    return {"status": "ingestion started"}
```

## Implementation

1. Choose a job scheduler (APScheduler or Celery)
2. Implement worker functions to call integrations
3. Track progress in `IngestRun` table
4. Add monitoring & alerting
