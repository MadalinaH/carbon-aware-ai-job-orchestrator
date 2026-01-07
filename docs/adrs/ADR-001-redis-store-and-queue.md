# ADR-001: Redis as Job Store and Message Queue

## Status
Accepted

## Context
The Carbon-Aware AI Job Orchestrator requires both persistent job metadata storage and asynchronous message queuing to decouple components (API, Scheduler, Workers). The system needs:
- Job state persistence across restarts
- Queue-based job routing (PENDING → FAST/ECO/DEFERRED)
- Simple deployment with minimal dependencies
- Fast read/write operations for scheduling decisions

## Decision
Use Redis for both job storage and message queuing:
- **Job Storage**: Hash structures `job:{job_id}` containing all job metadata (status, mode, timestamps, decision metadata, emissions, etc.)
- **Message Queues**: 
  - Lists: `queue:PENDING`, `queue:FAST`, `queue:ECO` (FIFO via LPUSH/RPOP)
  - Sorted Set: `queue:DEFERRED` (deadline as score, enables time-based release)

This unified approach provides simplicity, decoupling, and operational consistency.

## Consequences

### Positive
- **Simplicity**: Single technology stack reduces operational complexity
- **Decoupling**: Components communicate via Redis without direct coupling
- **Fast Operations**: O(1) hash lookups and O(1) list operations enable low-latency scheduling
- **Atomic Operations**: Redis transactions ensure consistency for job state updates
- **Deferred Jobs**: Sorted sets enable efficient deadline-based job release
- **Lightweight**: Minimal infrastructure footprint for checkpoint/demo scenarios

### Negative
- **KEYS Operation**: `/stats` endpoint uses `KEYS job:*` which blocks Redis; acceptable for small-scale deployments but not production-scale
- **Persistence**: Default Redis configuration may not guarantee durability (AOF/RDB persistence requires explicit configuration)
- **Scalability**: Single Redis instance becomes bottleneck at high job volumes
- **No Schema Validation**: Job hash fields are strings; type coercion handled in application code

## Alternatives Considered
1. **Separate Queue System (RabbitMQ/Kafka) + Database (PostgreSQL)**: More complex deployment, better durability guarantees, but overkill for checkpoint scope
2. **PostgreSQL-only**: ACID guarantees and schema validation, but lacks native queue semantics and requires polling
3. **In-memory only**: Faster but loses state on restart, unsuitable for job tracking

## Links
- Implementation: `services/api/main.py` (job creation), `services/scheduler/main.py` (queue operations)
- Redis Schema: Job hashes `job:{id}`, queues `queue:PENDING`, `queue:FAST`, `queue:ECO`, `queue:DEFERRED`
- Deployment: `k8s/redis.yaml`

