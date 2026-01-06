import os
import time
import json
import yaml
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import redis
from carbon import get_carbon_intensity

redis_host = os.getenv("REDIS_HOST", "redis")
policy_path = os.getenv("POLICY_PATH", "/app/policy.yaml")

# Connect to Redis
r = redis.Redis(host=redis_host, port=6379, db=0, decode_responses=True)

def wait_for_redis(max_retries=None, sleep_seconds=2):
    """Wait for Redis to be available before proceeding.
    
    Args:
        max_retries: Maximum number of retry attempts. None means retry indefinitely.
        sleep_seconds: Seconds to wait between retry attempts.
    """
    attempt = 0
    while True:
        try:
            r.ping()
            print(f"[scheduler] Redis connection established")
            return
        except Exception as e:
            attempt += 1
            if max_retries is not None and attempt > max_retries:
                print(f"[scheduler] Failed to connect to Redis after {max_retries} attempts: {e}")
                raise
            print(f"[scheduler] Redis not ready (attempt {attempt}), retrying in {sleep_seconds}s...")
            time.sleep(sleep_seconds)

# Load policy
def load_policy(path: str) -> Dict[str, Any]:
    """Load policy from YAML file."""
    with open(path, 'r') as f:
        return yaml.safe_load(f)

policy = load_policy(policy_path)
thresholds = policy['thresholds']
rules = policy['rules']
guardrails = policy['guardrails']

print(f"[scheduler] started (policy loaded from {policy_path})")
print(f"[scheduler] thresholds: low={thresholds['low']}, high={thresholds['high']}")
print(f"[scheduler] max_deferral_seconds: {guardrails['max_deferral_seconds']}")

# Wait for Redis to be ready
wait_for_redis()

def evaluate_condition(condition: str, carbon_intensity: int, urgency: str) -> bool:
    """Evaluate a policy rule condition."""
    if condition == "default":
        return True
    
    # Parse condition explicitly
    low = thresholds['low']
    high = thresholds['high']
    
    # Handle urgency == critical
    if "urgency == critical" in condition:
        if urgency != "critical":
            return False
        # If only urgency check, return True
        if condition.strip() == "urgency == critical":
            return True
        # Otherwise, continue to check carbon intensity part
    
    # Handle urgency == flexible
    if "urgency == flexible" in condition:
        if urgency != "flexible":
            return False
        # If only urgency check, return True
        if condition.strip() == "urgency == flexible":
            return True
        # Otherwise, continue to check carbon intensity part
    
    # Handle carbon intensity comparisons
    if "carbon_intensity < low" in condition:
        return carbon_intensity < low
    if "carbon_intensity > high" in condition:
        return carbon_intensity > high
    if "carbon_intensity >= low" in condition and "carbon_intensity <= high" in condition:
        return carbon_intensity >= low and carbon_intensity <= high
    
    # Fallback: try simple evaluation (for edge cases)
    try:
        condition = condition.replace("carbon_intensity", str(carbon_intensity))
        condition = condition.replace("low", str(low))
        condition = condition.replace("high", str(high))
        condition = condition.replace("urgency == critical", "True" if urgency == "critical" else "False")
        condition = condition.replace("urgency == flexible", "True" if urgency == "flexible" else "False")
        condition = condition.replace("AND", "and").replace("OR", "or")
        # Only evaluate if it looks safe (numbers and operators)
        if all(c in "0123456789<>=!&|()-.andorTrueFalse " for c in condition):
            return eval(condition)
    except:
        pass
    
    return False

def apply_policy(carbon_intensity: int, urgency: str) -> tuple[str, str]:
    """Apply policy rules to determine mode and rule_id."""
    for rule in rules:
        condition = rule['condition']
        if evaluate_condition(condition, carbon_intensity, urgency):
            return rule['mode'], rule['policy_rule_id']
    
    # Fallback (should not happen)
    return "ECO", "FALLBACK"

def enforce_guardrails(mode: str, urgency: str, defer_deadline_ts: Optional[float]) -> tuple[str, float, Optional[str], Optional[str]]:
    """Enforce guardrails: critical jobs never defer, max deferral time.
    
    Returns:
        (mode, defer_deadline_ts, guardrail_rule_id, guardrail_reason)
        guardrail_rule_id and guardrail_reason are None if no guardrail was applied.
    """
    guardrail_rule_id = None
    guardrail_reason = None
    
    # Guardrail: critical jobs never defer
    if urgency == "critical" and mode == "DEFER":
        mode = "ECO"
        defer_deadline_ts = None
        guardrail_rule_id = "GUARDRAIL_CRITICAL_OVERRIDE"
        guardrail_reason = "Critical jobs cannot be deferred; overriding to ECO to satisfy SLO guardrail."
        print(f"[scheduler] Guardrail: critical job cannot be deferred, forcing ECO")
    
    # Guardrail: check if deferred job exceeded deadline
    if mode == "DEFER":
        if defer_deadline_ts is None:
            defer_deadline_ts = time.time() + guardrails['max_deferral_seconds']
        elif time.time() > defer_deadline_ts:
            # Force schedule (prefer ECO)
            mode = "ECO"
            defer_deadline_ts = None
            guardrail_rule_id = "GUARDRAIL_MAX_DEFERRAL"
            guardrail_reason = "Maximum deferral window exceeded; forcing ECO execution to prevent starvation."
            print(f"[scheduler] Guardrail: deferral deadline exceeded, forcing ECO")
    
    return mode, defer_deadline_ts, guardrail_rule_id, guardrail_reason

def get_decision_reason(mode: str, policy_rule_id: str, carbon_intensity: int) -> str:
    """Generate human-readable decision reason."""
    reasons = {
        "CRITICAL_OVERRIDE": f"Scheduled in FAST mode because urgency is critical, per policy CRITICAL_OVERRIDE.",
        "LOW_CARBON_FAST": f"Scheduled in FAST mode because carbon intensity was low (ci={carbon_intensity}), per policy LOW_CARBON_FAST.",
        "HIGH_CARBON_ECO": f"Scheduled in ECO mode because carbon intensity was high (ci={carbon_intensity}), per policy HIGH_CARBON_ECO.",
        "MEDIUM_FLEX_DEFER": f"Deferred because carbon intensity was medium (ci={carbon_intensity}) and urgency is flexible, per policy MEDIUM_FLEX_DEFER.",
        "MEDIUM_DEFAULT_ECO": f"Scheduled in ECO mode as default for medium carbon intensity (ci={carbon_intensity}), per policy MEDIUM_DEFAULT_ECO.",
        "GUARDRAIL_CRITICAL_OVERRIDE": "Critical jobs cannot be deferred; overriding to ECO to satisfy SLO guardrail.",
        "GUARDRAIL_MAX_DEFERRAL": "Maximum deferral window exceeded; forcing ECO execution to prevent starvation."
    }
    return reasons.get(policy_rule_id, f"Scheduled in {mode} mode per policy {policy_rule_id}.")

def process_job(job_id: str, job_data: Dict[str, Any], carbon_intensity: int) -> None:
    """Process a job: apply policy, enforce guardrails, and enqueue.
    
    Args:
        job_id: Job identifier
        job_data: Job metadata dictionary
        carbon_intensity: Current carbon intensity value to use for policy evaluation
    """
    urgency = job_data.get('urgency', 'flexible')
    
    # Apply policy
    mode, policy_rule_id = apply_policy(carbon_intensity, urgency)
    
    # Get existing defer_deadline_ts if job was already deferred
    existing_defer_deadline = job_data.get('defer_deadline_ts')
    if existing_defer_deadline:
        try:
            existing_defer_deadline = float(existing_defer_deadline)
        except:
            existing_defer_deadline = None
    else:
        existing_defer_deadline = None
    
    # Enforce guardrails
    mode, defer_deadline_ts, guardrail_rule_id, guardrail_reason = enforce_guardrails(mode, urgency, existing_defer_deadline)
    
    # If guardrail was applied, use guardrail metadata; otherwise use policy metadata
    if guardrail_rule_id is not None:
        policy_rule_id = guardrail_rule_id
        decision_reason = guardrail_reason
    else:
        decision_reason = get_decision_reason(mode, policy_rule_id, carbon_intensity)
    
    # Set job status based on decision
    if mode == "DEFER":
        job_data['status'] = "DEFERRED"
    else:
        job_data['status'] = "SCHEDULED"
    
    # Update job metadata
    job_data['mode'] = mode
    job_data['decision_timestamp'] = datetime.utcnow().isoformat()
    job_data['carbon_intensity_at_decision'] = carbon_intensity
    job_data['policy_rule_id'] = policy_rule_id
    job_data['decision_reason'] = decision_reason
    job_data['updated_at'] = datetime.utcnow().isoformat()
    
    if defer_deadline_ts:
        job_data['defer_deadline_ts'] = defer_deadline_ts
    elif 'defer_deadline_ts' in job_data:
        del job_data['defer_deadline_ts']
    
    # Persist job to Redis
    job_key = f"job:{job_id}"
    r.hset(job_key, mapping={k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in job_data.items()})
    
    # Enqueue or defer
    if mode == "DEFER":
        # Add to deferred queue (sorted set with deadline as score)
        r.zadd("queue:DEFERRED", {job_id: defer_deadline_ts})
        print(f"[scheduler] Job {job_id} deferred until {datetime.fromtimestamp(defer_deadline_ts).isoformat()}")
    elif mode == "FAST":
        r.lpush("queue:FAST", job_id)
        print(f"[scheduler] Job {job_id} -> FAST queue (ci={carbon_intensity}, rule={policy_rule_id})")
    elif mode == "ECO":
        r.lpush("queue:ECO", job_id)
        print(f"[scheduler] Job {job_id} -> ECO queue (ci={carbon_intensity}, rule={policy_rule_id})")

def check_deferred_jobs(carbon_intensity: int) -> None:
    """Check deferred jobs and process those past their deadline or when carbon is low (green window).
    
    Args:
        carbon_intensity: Current carbon intensity value to use for green window detection
    """
    now = time.time()
    
    # Green window release: if carbon is low, release all deferred jobs
    if carbon_intensity < thresholds['low']:
        all_deferred = r.zrange("queue:DEFERRED", 0, -1)
        if all_deferred:
            print(f"[scheduler] Green window detected (ci={carbon_intensity} < {thresholds['low']}), releasing {len(all_deferred)} deferred job(s)")
            for job_id in all_deferred:
                r.zrem("queue:DEFERRED", job_id)
                job_key = f"job:{job_id}"
                job_data = r.hgetall(job_key)
                if job_data:
                    # Convert string values back to proper types
                    processed_data = {}
                    for k, v in job_data.items():
                        try:
                            processed_data[k] = json.loads(v)
                        except:
                            processed_data[k] = v
                    
                    # Re-process with guardrail enforcement
                    process_job(job_id, processed_data, carbon_intensity)
        return  # Skip deadline check if green window released jobs
    
    # Deadline release: get jobs past their deadline
    expired_jobs = r.zrangebyscore("queue:DEFERRED", 0, now)
    
    for job_id in expired_jobs:
        r.zrem("queue:DEFERRED", job_id)
        job_key = f"job:{job_id}"
        job_data = r.hgetall(job_key)
        if job_data:
            # Convert string values back to proper types
            processed_data = {}
            for k, v in job_data.items():
                try:
                    processed_data[k] = json.loads(v)
                except:
                    processed_data[k] = v
            
            # Re-process with guardrail enforcement (use same carbon intensity for consistency)
            process_job(job_id, processed_data, carbon_intensity)

# Main loop
while True:
    try:
        # Sample carbon intensity once per scheduler tick for consistency
        carbon_intensity = get_carbon_intensity()
        
        # Check deferred jobs first (using the sampled carbon intensity)
        check_deferred_jobs(carbon_intensity)
        
        # Process pending jobs (from queue:PENDING)
        job_id = r.rpop("queue:PENDING")
        if job_id:
            job_key = f"job:{job_id}"
            job_data = r.hgetall(job_key)
            if job_data:
                # Convert string values back to proper types
                processed_data = {}
                for k, v in job_data.items():
                    try:
                        processed_data[k] = json.loads(v)
                    except:
                        processed_data[k] = v
                
                # Process job using the same carbon intensity sampled at the start of this tick
                process_job(job_id, processed_data, carbon_intensity)
            else:
                print(f"[scheduler] Warning: Job {job_id} not found in store")
        
        time.sleep(1)
        
    except Exception as e:
        print(f"[scheduler] Error: {e}")
        time.sleep(2)

