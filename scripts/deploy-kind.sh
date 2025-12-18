#!/bin/bash
set -euo pipefail

CLUSTER_NAME="aiacc"

echo "=== Deploying to kind cluster: $CLUSTER_NAME ==="

# Check if kind cluster exists, create if it doesn't
if kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
    echo "✓ Cluster '$CLUSTER_NAME' already exists"
else
    echo "Creating kind cluster '$CLUSTER_NAME'..."
    kind create cluster --name "$CLUSTER_NAME"
fi

# Build Docker images
echo ""
echo "=== Building Docker images ==="
docker build -t api:latest ./services/api
docker build -t scheduler:latest ./services/scheduler
docker build -t worker:latest ./services/worker

# Load images into kind cluster
echo ""
echo "=== Loading images into kind cluster ==="
kind load docker-image api:latest --name "$CLUSTER_NAME"
kind load docker-image scheduler:latest --name "$CLUSTER_NAME"
kind load docker-image worker:latest --name "$CLUSTER_NAME"

# Apply Kubernetes manifests
echo ""
echo "=== Applying Kubernetes manifests ==="
kubectl apply -f ./k8s/

# Wait for API deployment to be available
echo ""
echo "=== Waiting for API deployment to be ready ==="
kubectl wait --for=condition=available --timeout=120s deployment/api || true

# Print status
echo ""
echo "=== Deployment Status ==="
kubectl get pods

echo ""
echo "=== Next Steps ==="
echo "To access the API service, run:"
echo "  kubectl port-forward service/api 8000:8000"
echo ""
echo "Then visit: http://localhost:8000"

