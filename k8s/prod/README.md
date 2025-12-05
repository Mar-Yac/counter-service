# Kubernetes Manifests (Reference Only)

**IMPORTANT**: These manifests are kept for **reference only**.

The actual deployment is managed via:
- **Helm Chart**: `helm/counter-service/` (source of truth)
- **Argo CD GitOps**: `k8s/argocd/counter-service-application.yaml`

## Why These Files Exist

These YAML manifests serve as:
1. **Reference**: Show what resources are deployed
2. **Documentation**: Understand the Kubernetes resources without Helm templating
3. **Learning**: See the raw Kubernetes manifests

## Current Status

These manifests have been updated to match the Helm chart implementation:
- Uses Redis for persistence
- Includes all security enhancements
- Includes topology spread constraints
- Includes graceful shutdown configuration

## Deployment

**Do NOT apply these manifests directly.** Instead:

### Option 1: Use Helm (Recommended)
```bash
helm install counter-service ./helm/counter-service -n prod
```

### Option 2: Use Argo CD (GitOps)
```bash
kubectl apply -f k8s/argocd/counter-service-application.yaml
```

Argo CD will automatically deploy using the Helm chart.

## Differences from Helm Chart

The Helm chart provides:
- **Templating**: Dynamic values via `values.yaml`
- **Dependencies**: Redis and Prometheus/Grafana as subcharts
- **Flexibility**: Easy configuration changes
- **Best Practices**: Standardized Helm structure

These raw manifests are static and don't include:
- Redis deployment (managed separately or via Helm dependency)
- Prometheus/Grafana (managed via Helm dependency)
- Dynamic configuration
- Subchart dependencies

## Files in This Directory

- `deployment.yaml` - Counter service deployment
- `service.yaml` - ClusterIP service
- `ingress.yaml` - NLB Ingress
- `hpa.yaml` - Horizontal Pod Autoscaler
- `pdb.yaml` - Pod Disruption Budget
- `serviceaccount.yaml` - ServiceAccount
- `namespace.yaml` - Namespace

