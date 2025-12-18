import os
import time

mode = os.getenv("MODE", "FAST")
redis_host = os.getenv("REDIS_HOST", "redis")

print(f"[worker-{mode}] started")

while True:
    print(f"[worker-{mode}] idle (stub) - waiting for jobs")
    time.sleep(3)

