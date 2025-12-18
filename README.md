# Carbon-Aware AI Job Orchestrator

A distributed system for orchestrating AI/ML jobs with carbon awareness, optimizing job scheduling based on real-time carbon intensity data.

## Use Cases

- **UC1**: Schedule AI training jobs during low-carbon periods to minimize environmental impact.
- **UC2**: Route urgent jobs to fast workers when carbon intensity is low.
- **UC3**: Defer non-urgent jobs when carbon intensity is high.
- **UC4**: Monitor and report carbon emissions from AI job execution.
- **UC5**: Dynamically scale worker pools (FAST/ECO) based on carbon intensity thresholds.

## Components

- **API Service**: REST API for job submission and management
- **Scheduler Service**: Carbon-aware job scheduling and optimization
- **Worker Service (FAST)**: High-performance worker for low-carbon periods
- **Worker Service (ECO)**: Energy-efficient worker for high-carbon periods
- **Redis**: Job queue and metadata storage

## Technology Stack

- **Python 3.11**: Core language
- **FastAPI**: REST API framework
- **Redis**: Queue and data store
- **Docker**: Containerization
- **Kubernetes (kind)**: Local cluster orchestration

## Repository Structure

```
.
├── services/
│   ├── api/              # API service
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   ├── scheduler/         # Scheduler service
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   └── worker/           # Worker service
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
├── docker-compose.yml
└── README.md
```

## How to Deploy (kind)

1. Ensure you have `kind`, `kubectl`, and `docker` installed.

2. Run the deployment script:
   ```bash
   ./scripts/deploy-kind.sh
   ```

   This will:
   - Create a kind cluster named "aiacc" (if it doesn't exist)
   - Build Docker images for all services
   - Load images into the kind cluster
   - Apply all Kubernetes manifests
   - Wait for the API deployment to be ready

3. Start port-forwarding:
   ```bash
   ./scripts/port-forward.sh
   ```

## How to Verify

Once port-forwarding is active, verify the deployment:

```bash
# Health check
curl http://localhost:8000/health

# List jobs (stub endpoint)
curl http://localhost:8000/jobs

# Submit a job (stub endpoint)
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"type": "analytics", "urgency": "normal"}'
```

## Note

**This checkpoint focuses on scaffolding + Kubernetes deployment; full job execution logic will be implemented later.**

