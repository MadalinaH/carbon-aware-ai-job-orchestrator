# Carbon-Aware AI Job Orchestrator

A Kubernetes-based orchestration system that automatically schedules AI workloads based on real-time carbon intensity, job urgency, and policy-driven guardrails. The system balances sustainability objectives with operational SLOs through intelligent job routing, deferral, and explainable decision-making.

## Project Definition and Overall Description

This project implements a carbon-aware AI job orchestration application that automatically decides when, where, and how AI workloads are executed based on carbon intensity, job urgency, and simple service-level objectives (SLOs). The system targets realistic AI platform scenarios where many workloads—such as batch inference, analytics, and report generation—are operationally flexible and can be scheduled to reduce emissions without changing models or user workflows.

**AI Jobs in This System**: An AI job represents a simulated workload unit with metadata (type, urgency), execution mode (FAST/ECO/DEFER), and tracked emissions. Jobs are stored as Redis hashes with full decision traceability, including carbon intensity at decision time, policy rule ID, and human-readable decision reasons. Workers simulate execution (sleep-based) and record duration and emissions metrics.

Users submit AI jobs through a REST API, providing metadata such as job type and urgency. Jobs are placed onto a lightweight message queue to decouple components and enable scalable, fault-tolerant processing. A central Scheduler continuously reads a simulated carbon-intensity signal and applies a policy-based decision engine. When carbon intensity is low, jobs are executed immediately on a high-performance containerized worker. When carbon intensity is high, non-critical jobs are routed to an energy-efficient worker with lower resource usage. Under medium carbon conditions, flexible jobs may be deferred until greener execution windows are available. Critical jobs always override carbon-based deferral to ensure SLO compliance.

Workers execute a representative AI workload (simulated inference or analytics) and record execution outcomes such as duration and execution mode, as well as CO₂ emissions where feasible. The system exposes job status and basic operational and sustainability metrics, allowing users to observe how carbon-aware decisions affect execution behaviour.

## Architecture Overview

### API Service
REST API endpoint for job submission, status queries, system metrics, and explainability. Handles user requests and provides the primary interface to the orchestration system. Exposes endpoints for job lifecycle management and observability.

**Endpoints**:
- `GET /health` - Health check
- `GET /` - API information and endpoint list
- `POST /jobs` - Submit a new job (requires `type`, `urgency` in request body)
- `GET /jobs` - List all jobs with full metadata
- `GET /jobs/{id}` - Get specific job by ID
- `GET /jobs/{id}/explain` - Get structured explanation for job's scheduling decision (transparency/responsible AI)
- `GET /stats` - System observability metrics (queue depths, job counts, performance, emissions)

### Scheduler Service
Central decision engine that continuously monitors carbon intensity signals and applies routing policies. Determines when and where jobs should execute based on carbon conditions and job urgency. Loads policy rules from `policy.yaml` at startup and evaluates them in priority order. Uses a carbon adapter (`services/scheduler/carbon.py`) to obtain carbon intensity values (simulated, replaceable with external APIs). Records decision metadata (`policy_rule_id`, `decision_reason`, `carbon_intensity_at_decision`) for full traceability.

### Worker FAST / Worker ECO
Containerized workers that consume jobs from Redis queues and execute simulated AI workloads:
- **Worker FAST**: High-performance worker optimized for low-latency execution. Consumes from `queue:FAST`, simulates ~1s execution time, records higher emissions (0.002 kg per 1000ms).
- **Worker ECO**: Energy-efficient worker with lower resource usage. Consumes from `queue:ECO`, simulates ~3s execution time, records lower emissions (0.001 kg per 1000ms).

Both workers update job status (RUNNING → DONE), record `duration_ms` and `emissions_kg`, and preserve decision metadata.

### Redis (Job Store + Message Queues)
Unified storage and messaging layer:
- **Job Storage**: Hash structures `job:{job_id}` containing all metadata (status, mode, timestamps, decision metadata, emissions, result)
- **Message Queues**:
  - `queue:PENDING` (List) - Newly submitted jobs awaiting scheduling
  - `queue:FAST` (List) - Jobs routed to high-performance execution
  - `queue:ECO` (List) - Jobs routed to energy-efficient execution
  - `queue:DEFERRED` (Sorted Set) - Deferred jobs with deadline timestamp as score

Services access Redis via Kubernetes Service DNS name `redis` on port 6379.

## Architecturally Significant Use Cases (ASUCs)

These use cases describe the external behavior of the system from a user/operator perspective. The sequence diagrams (below) show the internal realization of these use cases.

### UC1 – Submit AI Job (ASUC)
Users submit AI jobs through the API service, providing metadata including job type and urgency level. The API validates the request, creates a job record in Redis (`job:{id}` hash), and enqueues the job ID to `queue:PENDING`. This use case establishes the entry point for the system and demonstrates the decoupled architecture where job submission is independent of execution scheduling.

### UC2 – Carbon-Aware Scheduling Decision (ASUC)
The Scheduler continuously monitors carbon intensity signals (via carbon adapter) and applies policy-based routing decisions. For each job in `queue:PENDING`, the scheduler samples carbon intensity once per tick, evaluates policy rules in priority order, enforces guardrails (critical override, max deferral), and routes jobs to `queue:FAST`, `queue:ECO`, or `queue:DEFERRED`. Decision metadata is persisted to the job hash. This use case is architecturally significant as it centralizes the carbon-aware decision logic, enabling flexible policy updates without modifying worker implementations.

### UC3 – Execute AI Job (ASUC)
Workers consume jobs from their assigned queues (`queue:FAST` or `queue:ECO`) using blocking pop operations. Workers update job status to RUNNING, simulate execution time, record duration and emissions, then update status to DONE with completion metadata. This use case demonstrates the separation between scheduling logic and execution, allowing different worker types to be scaled independently based on carbon conditions.

### UC4 – Deferred Job Release (ASUC)
When carbon intensity is medium and jobs are flexible, the Scheduler defers execution until more favorable conditions. Deferred jobs are stored in `queue:DEFERRED` with deadline timestamps. The scheduler releases deferred jobs when: (a) carbon intensity drops below threshold ("green window release"), or (b) deadline is exceeded (guardrail enforcement). This use case illustrates the system's ability to balance operational requirements with sustainability objectives through intelligent job queuing and starvation prevention.

### UC5 – Observe System State (ASUC)
Users and operators query job status, execution metrics, and carbon emissions data through the API. The `/jobs` and `/jobs/{id}` endpoints return full job metadata including decision traceability. The `/stats` endpoint provides aggregate metrics (queue depths, job counts by status/mode, average duration, total emissions). The `/jobs/{id}/explain` endpoint provides structured explainability information. This use case demonstrates observability and the system's ability to provide transparency into carbon-aware decision-making and its impact on execution behavior.

## Diagrams

### Use Case Diagram
![Use Case Diagram](docs/diagrams/uc_0_diag.png)

### Sequence Diagrams (Internal Realization)

#### UC1 – Submit AI Job
![UC1 Sequence Diagram](docs/diagrams/uc1.png)
Sequence diagram showing API receiving job submission, storing job hash in Redis, and enqueuing to queue:PENDING.

#### UC2 – Carbon-Aware Scheduling Decision
![UC2 Sequence Diagram](docs/diagrams/uc2.png)
Sequence diagram showing scheduler sampling carbon intensity, evaluating policy rules, enforcing guardrails, and routing jobs to appropriate queues.

#### UC3 – Execute AI Job
![UC3 Sequence Diagram](docs/diagrams/uc3.png)
Sequence diagram showing worker consuming job from queue, updating status to RUNNING, executing workload, and updating status to DONE with metrics.

#### UC4 – Deferred Job Release
![UC4 Sequence Diagram](docs/diagrams/uc4.png)
Sequence diagram showing scheduler detecting green window (low carbon) or deadline expiration, releasing deferred jobs, and routing them for execution.

#### UC5 – Observe System State
![UC5 Sequence Diagram](docs/diagrams/uc5.png)
Sequence diagram showing API querying Redis for job data and returning structured responses with metadata and metrics.

### Component Diagram
![Component Diagram](docs/diagrams/comp_diag.png)

### Deployment Diagram
![Deployment Diagram](docs/diagrams/deployment_diag.png)

## Responsible AI / Sustainability

### Policy-as-Code Transparency
Scheduling decisions are driven by `policy.yaml` (loaded at scheduler startup via `POLICY_PATH`). Policy rules include thresholds (low=200, high=400 gCO2/kWh) and ordered condition→mode mappings. Every scheduling decision records:
- `policy_rule_id`: Identifier of the rule that triggered the decision (e.g., `LOW_CARBON_FAST`, `HIGH_CARBON_ECO`, `GUARDRAIL_CRITICAL_OVERRIDE`)
- `decision_reason`: Human-readable explanation of the decision
- `carbon_intensity_at_decision`: Carbon intensity value used for the decision

### Guardrails
Two guardrails ensure SLO compliance and prevent starvation:
1. **Critical Job Override**: Jobs with `urgency == "critical"` are never deferred, forced to ECO (or FAST) mode regardless of carbon conditions
2. **Max Deferral Window**: Deferred jobs have a maximum wait time (`max_deferral_seconds: 600`); expired jobs are forced to ECO execution

Guardrail applications are recorded with `policy_rule_id` starting with `GUARDRAIL_` for transparency.

### Explainability Endpoint
`GET /jobs/{id}/explain` returns structured explainability information:
- Job metadata (status, mode, urgency, job_type)
- Decision traceability (carbon_intensity_at_decision, policy_rule_id, decision_reason)
- Guardrail indication (`guardrail_applied` flag)
- Policy thresholds and human-friendly notes

This enables users to understand why jobs were scheduled in a particular mode and whether guardrails were applied.

### Emissions Tracking
Jobs record `emissions_kg` upon completion (simulated based on duration and execution mode). The `/stats` endpoint aggregates total emissions across all completed jobs, providing sustainability metrics.

## Observability

The `GET /stats` endpoint provides lightweight observability metrics:

- **Queue Depths**: Current lengths of `queue:PENDING`, `queue:FAST`, `queue:ECO`, and count of `queue:DEFERRED`
- **Job Statistics**: 
  - Total job count
  - Counts by status (QUEUED, SCHEDULED, DEFERRED, RUNNING, DONE)
  - Counts by mode (FAST, ECO, DEFER, null for unscheduled)
- **Performance**: Average execution duration (ms) across completed jobs
- **Sustainability**: Total emissions (kg) across all completed jobs

Note: This endpoint uses Redis `KEYS` operation which is acceptable for demo/checkpoint scale but not recommended for production at high job volumes.

## Architecture Decision Records (ADRs)

Cross-cutting architectural decisions are documented in ADRs:

- **[ADR-001: Redis as Job Store and Message Queue](docs/adrs/ADR-001-redis-store-and-queue.md)**: Unified Redis usage for job storage (hashes) and message queuing (lists + sorted set) for simplicity and decoupling.
- **[ADR-002: Policy-as-Code for Carbon-Aware Scheduling](docs/adrs/ADR-002-policy-as-code-scheduling.md)**: YAML-based policy configuration enabling transparency, tunability, and decision traceability.
- **[ADR-003: Job Deferral and Guardrails](docs/adrs/ADR-003-deferral-and-guardrails.md)**: Deferral mechanism with guardrails (critical override, max deferral window) and green window release for starvation prevention.

## Technology Stack

- **Python 3.11**: Core programming language for all services
- **FastAPI**: REST API framework for the API service
- **Redis**: Job store and message queue implementation
- **Docker**: Containerization platform for service packaging
- **Kubernetes (kind)**: Local Kubernetes cluster for orchestration and deployment
- **kubectl**: Command-line tool for Kubernetes cluster management

## Running Locally (Kind)

### Prerequisites
- Docker
- kubectl
- kind

### Deployment

1. **Deploy to kind cluster**:
   ```bash
   chmod +x scripts/*.sh
   ./scripts/deploy-kind.sh
   ```

   This script:
   - Creates a kind cluster named "aiacc" (if it doesn't exist)
   - Builds Docker images for all services
   - Loads images into the kind cluster
   - Applies Kubernetes manifests from `k8s/`
   - Waits for API deployment to be ready

2. **Port-forward API service**:
   ```bash
   ./scripts/port-forward.sh
   ```
   
   Or manually:
   ```bash
   kubectl port-forward svc/api 8000:8000
   ```

3. **Verify deployment**:
   ```bash
   kubectl get pods
   curl http://localhost:8000/health
   ```

### Example API Usage

**Submit a job**:
```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"type": "inference", "urgency": "flexible"}'
```

**List all jobs**:
```bash
curl http://localhost:8000/jobs | python -m json.tool
```

**Get specific job**:
```bash
curl http://localhost:8000/jobs/{job_id} | python -m json.tool
```

**Get job explanation**:
```bash
curl http://localhost:8000/jobs/{job_id}/explain | python -m json.tool
```

**Get system stats**:
```bash
curl http://localhost:8000/stats | python -m json.tool
```

## Repository Structure

```
.
├── services/
│   ├── api/              # API service implementation
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   ├── scheduler/         # Scheduler service implementation
│   │   ├── main.py
│   │   ├── carbon.py      # Carbon intensity adapter
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   └── worker/           # Worker service implementation
│       ├── main.py
│       ├── requirements.txt
│       └── Dockerfile
├── k8s/                  # Kubernetes manifests
│   ├── redis.yaml
│   ├── api.yaml
│   ├── scheduler.yaml
│   ├── worker-fast.yaml
│   └── worker-eco.yaml
├── scripts/              # Deployment scripts
│   ├── deploy-kind.sh
│   ├── deploy-k8s.sh
│   └── port-forward.sh
├── docs/
│   ├── diagrams/         # Architecture and sequence diagrams
│   │   ├── uc_0_diag.png
│   │   ├── uc1.png
│   │   ├── uc2.png
│   │   ├── uc3.png
│   │   ├── uc4.png
│   │   ├── uc5.png
│   │   ├── comp_diag.png
│   │   └── deployment_diag.png
│   └── adrs/             # Architecture Decision Records
│       ├── ADR-001-redis-store-and-queue.md
│       ├── ADR-002-policy-as-code-scheduling.md
│       └── ADR-003-deferral-and-guardrails.md
├── policy.yaml           # Policy-as-code configuration
├── docker-compose.yml
└── README.md
```

## Notes / Limitations

- **Demo-Scale Redis**: The system uses Redis `KEYS` operation in `/stats` endpoint, which is acceptable for checkpoint/demo scenarios but not recommended for production at high job volumes.
- **Simulated Carbon Intensity**: Carbon intensity is currently simulated (random 100-600 gCO2/kWh or fixed via `CARBON_FIXED` env var). The carbon adapter (`services/scheduler/carbon.py`) can be replaced with external API integrations (e.g., Electricity Maps, WattTime).
- **Simulated Workloads**: Workers simulate execution via sleep operations. Real workloads would require actual AI inference/analytics code.
- **Single Policy**: One `policy.yaml` per scheduler instance; no per-tenant policy support.
- **Redis Persistence**: Default Redis configuration may not guarantee durability; production deployments should configure AOF/RDB persistence.
