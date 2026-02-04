"""Background job workers for data ingestion."""

# TODO: Implement background ingestion jobs
#
# This module will contain scheduled tasks for:
# 1. Fetching data from external sources (CISA KEV, NVD, Shodan, etc.)
# 2. Parsing and normalizing data
# 3. Storing results in IngestRun table
# 4. Running anomaly detection
#
# Options for job scheduling:
# - APScheduler (lightweight, built-in scheduling)
# - Celery + Redis (distributed, for scaling)
# - FastAPI BackgroundTasks (simple, one-off tasks)
#
# Example with APScheduler:
#
# from apscheduler.schedulers.asyncio import AsyncIOScheduler
# from app.integrations.cisa_kev import CISAClient
#
# scheduler = AsyncIOScheduler()
#
# @scheduler.scheduled_job('interval', minutes=60)
# async def ingest_cisa_kev():
#     client = CISAClient()
#     data = await client.fetch_vulnerabilities()
#     # Save to database
#
# # In app/main.py:
# @app.on_event("startup")
# async def startup_jobs():
#     scheduler.start()
#
# @app.on_event("shutdown")
# async def shutdown_jobs():
#     scheduler.shutdown()
