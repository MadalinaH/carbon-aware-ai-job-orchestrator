import os
import time
import json
import random
from datetime import datetime
from typing import Dict, Any, Optional

import redis

mode = os.getenv("MODE", "FAST")
redis_host = os.getenv("REDIS_HOST", "redis")

# Determine queue name based on mode
queue_name = f"queue:{mode}"

# Execution parameters based on mode
if mode == "FAST":
    min_sleep = 0.5
    max_sleep = 1.5
    emissions_per_ms = 0.002 / 1000  # 0.002 kg per 1000ms
else:  # ECO
    min_sleep = 2.0
    max_sleep = 4.0
    emissions_per_ms = 0.001 / 1000  # 0.001 kg per 1000ms

print(f"[worker-{mode}] started (queue: {queue_name})")

# Connect to Redis with retry logic
def get_redis_connection():
    """Get Redis connection with retry logic. Retries indefinitely until connection succeeds."""
    retry_delay = 2
    attempt = 0
    
    while True:
        attempt += 1
        try:
            r = redis.Redis(host=redis_host, port=6379, db=0, decode_responses=True)
            # Test connection
            r.ping()
            print(f"[worker-{mode}] Redis connection established")
            return r
        except Exception as e:
            print(f"[worker-{mode}] Redis not ready (attempt {attempt}), retrying in {retry_delay}s...")
            time.sleep(retry_delay)

r = get_redis_connection()

idle_counter = 0
idle_log_interval = 10  # Log idle message every 10 loops

while True:
    try:
        # Blocking pop with 5 second timeout
        result = r.brpop(queue_name, timeout=5)
        
        if result is None:
            # No job received (timeout)
            idle_counter += 1
            if idle_counter >= idle_log_interval:
                print(f"[worker-{mode}] idle - waiting for jobs")
                idle_counter = 0
            continue
        
        # Extract job_id from result (BRPOP returns (queue_name, job_id))
        _, job_id = result
        
        # Load job hash
        job_key = f"job:{job_id}"
        job_data = r.hgetall(job_key)
        
        if not job_data:
            print(f"[worker-{mode}] Warning: Job {job_id} not found in store, skipping")
            continue
        
        # Convert string values back to proper types for processing
        processed_data = {}
        for k, v in job_data.items():
            try:
                processed_data[k] = json.loads(v)
            except:
                processed_data[k] = v
        
        # Update status to RUNNING
        start_time = time.monotonic()
        now_iso = datetime.utcnow().isoformat()
        
        r.hset(job_key, mapping={
            "status": "RUNNING",
            "updated_at": now_iso
        })
        
        # Simulate execution time
        sleep_duration = random.uniform(min_sleep, max_sleep)
        time.sleep(sleep_duration)
        
        # Calculate duration
        end_time = time.monotonic()
        duration_ms = int((end_time - start_time) * 1000)
        
        # Calculate emissions (placeholder, based on duration)
        emissions_kg = round(duration_ms * emissions_per_ms, 6)
        
        # Update job with completion data
        completion_iso = datetime.utcnow().isoformat()
        r.hset(job_key, mapping={
            "status": "DONE",
            "updated_at": completion_iso,
            "duration_ms": str(duration_ms),
            "emissions_kg": str(emissions_kg),
            "result": "ok"
        })
        
        # Log completion
        print(f"[worker-{mode}] Job {job_id} completed: duration={duration_ms}ms, emissions={emissions_kg}kg")
        
        # Reset idle counter after processing a job
        idle_counter = 0
        
    except redis.ConnectionError as e:
        print(f"[worker-{mode}] Redis connection error: {e}, reconnecting...")
        time.sleep(2)
        r = get_redis_connection()
    except Exception as e:
        print(f"[worker-{mode}] Error processing job: {e}")
        time.sleep(1)
