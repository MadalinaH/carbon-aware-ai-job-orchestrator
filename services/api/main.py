import os
import uuid
import json
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import redis

app = FastAPI()

redis_host = os.getenv("REDIS_HOST", "redis")
r = redis.Redis(host=redis_host, port=6379, db=0, decode_responses=True)


class JobRequest(BaseModel):
    type: Optional[str] = None
    urgency: Optional[str] = "flexible"


class JobResponse(BaseModel):
    job_id: str
    type: Optional[str]
    urgency: str
    status: str
    mode: Optional[str]
    created_at: str
    updated_at: str
    decision_timestamp: Optional[str]
    carbon_intensity_at_decision: Optional[int]
    policy_rule_id: Optional[str]
    decision_reason: Optional[str]
    defer_deadline_ts: Optional[float]
    duration_ms: Optional[int]
    emissions_kg: Optional[float]
    result: Optional[str]


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
            "POST /jobs": "Submit a new job",
            "GET /jobs": "List all jobs",
            "GET /jobs/{id}": "Get job by ID",
            "GET /jobs/{id}/explain": "Get explanation for job decision",
            "GET /stats": "Get system observability metrics"
        }
    }


def job_dict_to_response(job_id: str, job_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Redis job data to response format."""
    result = {
        "job_id": job_id,
        "type": job_data.get("type"),
        "urgency": job_data.get("urgency", "flexible"),
        "status": job_data.get("status", "QUEUED"),
        "mode": job_data.get("mode"),
        "created_at": job_data.get("created_at"),
        "updated_at": job_data.get("updated_at"),
        "decision_timestamp": job_data.get("decision_timestamp"),
        "carbon_intensity_at_decision": job_data.get("carbon_intensity_at_decision"),
        "policy_rule_id": job_data.get("policy_rule_id"),
        "decision_reason": job_data.get("decision_reason"),
        "duration_ms": job_data.get("duration_ms"),
        "emissions_kg": job_data.get("emissions_kg"),
        "result": job_data.get("result")
    }
    
    # Handle defer_deadline_ts (may be string or float)
    defer_deadline = job_data.get("defer_deadline_ts")
    if defer_deadline:
        try:
            result["defer_deadline_ts"] = float(defer_deadline)
        except:
            result["defer_deadline_ts"] = None
    else:
        result["defer_deadline_ts"] = None
    
    # Convert numeric fields
    if result["carbon_intensity_at_decision"]:
        try:
            result["carbon_intensity_at_decision"] = int(result["carbon_intensity_at_decision"])
        except:
            pass
    
    if result["duration_ms"]:
        try:
            result["duration_ms"] = int(result["duration_ms"])
        except:
            pass
    
    if result["emissions_kg"]:
        try:
            result["emissions_kg"] = float(result["emissions_kg"])
        except:
            pass
    
    return result


@app.post("/jobs")
async def create_job(job: JobRequest):
    """Create a new job and enqueue it for scheduling."""
    job_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    
    # Initialize job with all metadata fields
    job_data = {
        "job_id": job_id,
        "type": job.type,
        "urgency": job.urgency or "flexible",
        "status": "QUEUED",
        "mode": None,  # Will be set by scheduler
        "created_at": now,
        "updated_at": now,
        "decision_timestamp": None,  # Will be set by scheduler
        "carbon_intensity_at_decision": None,  # Will be set by scheduler
        "policy_rule_id": None,  # Will be set by scheduler
        "decision_reason": None,  # Will be set by scheduler
        "defer_deadline_ts": None,  # Will be set by scheduler if deferred
        "duration_ms": None,  # Will be set by worker
        "emissions_kg": None,  # Will be set by worker
        "result": None  # Will be set by worker
    }
    
    # Store job in Redis
    job_key = f"job:{job_id}"
    r.hset(job_key, mapping={k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in job_data.items()})
    
    # Enqueue to pending queue for scheduler
    r.lpush("queue:PENDING", job_id)
    
    return {
        "job_id": job_id,
        "status": "QUEUED"
    }


@app.get("/jobs", response_model=List[Dict[str, Any]])
async def list_jobs():
    """List all jobs."""
    jobs = []
    
    # Get all job keys
    job_keys = r.keys("job:*")
    
    for job_key in job_keys:
        job_id = job_key.replace("job:", "")
        job_data = r.hgetall(job_key)
        
        if job_data:
            # Convert string values back to proper types
            processed_data = {}
            for k, v in job_data.items():
                try:
                    processed_data[k] = json.loads(v)
                except:
                    processed_data[k] = v
            
            jobs.append(job_dict_to_response(job_id, processed_data))
    
    return jobs


@app.get("/jobs/{job_id}", response_model=Dict[str, Any])
async def get_job(job_id: str):
    """Get a specific job by ID."""
    job_key = f"job:{job_id}"
    job_data = r.hgetall(job_key)
    
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Convert string values back to proper types
    processed_data = {}
    for k, v in job_data.items():
        try:
            processed_data[k] = json.loads(v)
        except:
            processed_data[k] = v
    
    return job_dict_to_response(job_id, processed_data)


@app.get("/jobs/{job_id}/explain")
async def explain_job(job_id: str):
    """Get structured explanation for a job's scheduling decision (transparency/responsible AI)."""
    job_key = f"job:{job_id}"
    job_data = r.hgetall(job_key)
    
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Convert string values back to proper types
    processed_data = {}
    for k, v in job_data.items():
        try:
            processed_data[k] = json.loads(v)
        except:
            processed_data[k] = v
    
    # Extract fields
    status = processed_data.get("status", "UNKNOWN")
    mode = processed_data.get("mode")
    urgency = processed_data.get("urgency", "flexible")
    job_type = processed_data.get("type")
    policy_rule_id = processed_data.get("policy_rule_id")
    decision_reason = processed_data.get("decision_reason")
    
    # Parse carbon_intensity_at_decision
    carbon_intensity_at_decision = processed_data.get("carbon_intensity_at_decision")
    if carbon_intensity_at_decision:
        try:
            carbon_intensity_at_decision = int(carbon_intensity_at_decision)
        except (ValueError, TypeError):
            carbon_intensity_at_decision = None
    else:
        carbon_intensity_at_decision = None
    
    # Parse defer_deadline_ts
    defer_deadline_ts = processed_data.get("defer_deadline_ts")
    if defer_deadline_ts:
        try:
            defer_deadline_ts = float(defer_deadline_ts)
        except (ValueError, TypeError):
            defer_deadline_ts = None
    else:
        defer_deadline_ts = None
    
    # Determine if guardrail was applied
    guardrail_applied = False
    if policy_rule_id and policy_rule_id.startswith("GUARDRAIL_"):
        guardrail_applied = True
    
    # Default decision reason if missing
    if not decision_reason:
        decision_reason = "Job is queued and awaiting scheduling decision."
    
    # Policy thresholds (matching policy.yaml)
    policy_thresholds = {
        "low": 200,
        "high": 400
    }
    
    # Generate human-friendly notes
    notes_parts = []
    if status == "QUEUED":
        notes_parts.append("Job is queued and awaiting scheduling decision.")
    elif status == "DEFERRED":
        notes_parts.append("Job execution was deferred to wait for lower carbon intensity.")
        if defer_deadline_ts:
            notes_parts.append(f"Will be scheduled by {datetime.fromtimestamp(defer_deadline_ts).isoformat()}.")
    elif status == "SCHEDULED":
        if mode == "FAST":
            notes_parts.append("Job scheduled for immediate execution on high-performance worker.")
        elif mode == "ECO":
            notes_parts.append("Job scheduled for execution on energy-efficient worker.")
    elif status == "RUNNING":
        notes_parts.append("Job is currently executing.")
    elif status == "DONE":
        notes_parts.append("Job execution completed.")
        if carbon_intensity_at_decision:
            if carbon_intensity_at_decision < policy_thresholds["low"]:
                notes_parts.append(f"Executed during low carbon period (ci={carbon_intensity_at_decision} < {policy_thresholds['low']}).")
            elif carbon_intensity_at_decision > policy_thresholds["high"]:
                notes_parts.append(f"Executed during high carbon period (ci={carbon_intensity_at_decision} > {policy_thresholds['high']}).")
            else:
                notes_parts.append(f"Executed during medium carbon period (ci={carbon_intensity_at_decision}).")
    
    if guardrail_applied:
        notes_parts.append("A guardrail was applied to ensure SLO compliance or prevent job starvation.")
    
    notes = " ".join(notes_parts) if notes_parts else "No additional information available."
    
    return {
        "job_id": job_id,
        "status": status,
        "mode": mode,
        "urgency": urgency,
        "job_type": job_type,
        "carbon_intensity_at_decision": carbon_intensity_at_decision,
        "policy_rule_id": policy_rule_id,
        "decision_reason": decision_reason,
        "guardrail_applied": guardrail_applied,
        "defer_deadline_ts": defer_deadline_ts,
        "explainability": {
            "policy_thresholds": policy_thresholds,
            "notes": notes
        }
    }


@app.get("/stats")
async def get_stats():
    """Lightweight observability endpoint for demo/checkpoint purposes.
    
    Returns queue depths, job statistics, performance metrics, and sustainability metrics.
    Note: This endpoint uses KEYS operation which is suitable for small-scale deployments.
    """
    try:
        # Queue depths - handle Redis errors gracefully
        try:
            queue_depths = {
                "pending": r.llen("queue:PENDING"),
                "fast": r.llen("queue:FAST"),
                "eco": r.llen("queue:ECO"),
                "deferred": r.zcard("queue:DEFERRED")
            }
        except Exception as e:
            queue_depths = {"pending": 0, "fast": 0, "eco": 0, "deferred": 0}
        
        # Job statistics
        try:
            job_keys = r.keys("job:*")
            total_jobs = len(job_keys)
        except Exception:
            job_keys = []
            total_jobs = 0
        
        counts_by_status = {}
        counts_by_mode = {}
        durations = []
        total_emissions = 0.0
        
        for job_key in job_keys:
            try:
                job_data = r.hgetall(job_key)
                if not job_data:
                    continue
                
                # Count by status
                status = job_data.get("status", "UNKNOWN")
                counts_by_status[status] = counts_by_status.get(status, 0) + 1
                
                # Count by mode
                mode = job_data.get("mode")
                if mode is None or mode == "None" or mode == "":
                    mode = None
                counts_by_mode[mode] = counts_by_mode.get(mode, 0) + 1
                
                # Collect duration for average calculation
                duration_ms = job_data.get("duration_ms")
                if duration_ms:
                    try:
                        duration_val = int(duration_ms)
                        if duration_val > 0:
                            durations.append(duration_val)
                    except (ValueError, TypeError):
                        pass
                
                # Sum emissions
                emissions_kg = job_data.get("emissions_kg")
                if emissions_kg:
                    try:
                        emissions_val = float(emissions_kg)
                        if emissions_val > 0:
                            total_emissions += emissions_val
                    except (ValueError, TypeError):
                        pass
            except Exception:
                # Skip individual job errors
                continue
        
        # Calculate average duration
        avg_duration_ms = None
        if durations:
            avg_duration_ms = round(sum(durations) / len(durations), 2)
        
        return {
            "queue_depths": queue_depths,
            "jobs": {
                "total_jobs": total_jobs,
                "counts_by_status": counts_by_status,
                "counts_by_mode": counts_by_mode
            },
            "performance": {
                "avg_duration_ms": avg_duration_ms
            },
            "sustainability": {
                "total_emissions_kg": round(total_emissions, 6)
            }
        }
    except Exception as e:
        # Return error response instead of crashing
        return {
            "error": str(e),
            "queue_depths": {"pending": 0, "fast": 0, "eco": 0, "deferred": 0},
            "jobs": {"total_jobs": 0, "counts_by_status": {}, "counts_by_mode": {}},
            "performance": {"avg_duration_ms": None},
            "sustainability": {"total_emissions_kg": 0.0}
        }
