#!/bin/bash
set -euo pipefail

echo "=== Applying Kubernetes manifests ==="
kubectl apply -f ./k8s/

echo ""
echo "=== Pods Status ==="
kubectl get pods

echo ""
echo "=== Services Status ==="
kubectl get svc

