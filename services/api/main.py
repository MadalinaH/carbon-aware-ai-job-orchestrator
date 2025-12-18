import os
import uuid
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

redis_host = os.getenv("REDIS_HOST", "redis")


class JobRequest(BaseModel):
    type: Optional[str] = None
    urgency: Optional[str] = None


@app.on_event("startup")
async def startup_event():
    print(f"API started (Redis host: {redis_host})")


@app.get("/health")
async def health():
    return {"ok": True, "service": "api"}


@app.get("/")
async def root():
    return {
        "system": "Carbon-Aware AI Job Orchestrator",
        "service": "API",
        "endpoints": {
            "GET /health": "Health check",
            "GET /": "This endpoint",
            "POST /jobs": "Submit a new job (stub)",
            "GET /jobs": "List all jobs (stub)"
        }
    }


@app.post("/jobs")
async def create_job(job: JobRequest):
    job_id = str(uuid.uuid4())
    return {
        "job_id": job_id,
        "status": "QUEUED (stub)"
    }


@app.get("/jobs")
async def list_jobs():
    return {
        "jobs": [],
        "note": "stub endpoint for checkpoint scaffolding"
    }

