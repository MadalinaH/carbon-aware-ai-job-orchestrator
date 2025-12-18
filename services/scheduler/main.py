import os
import random
import time

redis_host = os.getenv("REDIS_HOST", "redis")
low_threshold = int(os.getenv("LOW_THRESHOLD", "200"))
high_threshold = int(os.getenv("HIGH_THRESHOLD", "400"))
carbon_fixed = os.getenv("CARBON_FIXED")

print("[scheduler] started")

while True:
    # Compute carbon intensity
    if carbon_fixed and int(carbon_fixed) > 0:
        ci = int(carbon_fixed)
    else:
        ci = random.randint(100, 600)
    
    # Determine mode based on thresholds
    if ci < low_threshold:
        mode = "FAST"
    elif ci > high_threshold:
        mode = "ECO"
    else:
        mode = "DEFER"
    
    print(f"Carbon intensity: {ci} -> Mode: {mode}")
    
    time.sleep(2)

